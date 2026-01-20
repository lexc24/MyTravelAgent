# destination_search/logic/recommendation_engine.py

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from typing_extensions import Literal

# ------------------------------------------------------------
# 1) LLM setup: keep Gemini as requested (no try/except)
# ------------------------------------------------------------
load_dotenv()
try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0,
    )

except:
    llm = None  # Will be mocked in tests

# ------------------------------------------------------------
# 2) Tunables (small, predictable)
# ------------------------------------------------------------
MAX_Q_ITERS = 1  # one refinement pass for clarifying questions
MAX_DEST_ITERS = 2  # up to two refinements for destinations (best-of-three)

# ------------------------------------------------------------
# 3) Graph state
# ------------------------------------------------------------
class State(TypedDict, total=False):
    # You already use these in your flow:
    info: str  # accumulated user context
    feedback: str  # re-used for question text in some flows
    question_queue: List[str]  # questions to present to user
    destinations: str  # raw text block of final recs

    question_iteration: int
    qe_grade: Literal["pass", "fail"]
    qe_notes: List[str]

    dest_iteration: int
    dest_grade: Literal["pass", "fail"]
    dest_notes: List[str]

    question_history: List[Dict[str, str]]  # {"q": str, "a": str}


# ------------------------------------------------------------
# 4) Parsers & light prechecks
# ------------------------------------------------------------
_Q_LINE = re.compile(r"^\s*(\d+)\.\s+(.+?\?)\s*$")


def parse_questions(text: str, max_n: int = 6) -> List[str]:
    qs: List[str] = []
    for line in text.splitlines():
        m = _Q_LINE.match(line)
        if not m:
            continue
        qs.append(m.group(2).strip())
    # de-dup, preserve order
    seen = set()
    out: List[str] = []
    for q in qs:
        k = q.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(q)
    return out[:max_n]


def precheck_questions(qs: List[str]) -> List[str]:
    issues: List[str] = []
    if not qs:
        issues.append("No parseable questions.")
        return issues
    if len(qs) > 6:
        issues.append("More than 6 questions.")
    if any(not q.endswith("?") for q in qs):
        issues.append("All questions must end with '?'.")
    # simple redundancy n-gram overlap(redundeacny with shared sequences)
    norm = [re.sub(r"[^a-z0-9 ]+", "", q.lower()) for q in qs]
    for i in range(len(norm)):
        ai = set(norm[i].split())
        for j in range(i + 1, len(norm)):
            aj = set(norm[j].split())
            if ai and aj and len(ai & aj) / max(1, len(ai | aj)) > 0.7:
                issues.append("Questions are redundant; merge similar ones.")
                return issues
    return issues


def parse_destinations(text: str) -> List[Dict[str, str]]:
    """
    Expected:
      1. City, Country
         1–2 sentences of specifics
      2. ...
      3. ...
    """
    items: List[Dict[str, str]] = []
    blocks = re.split(r"\n\s*(?=\d+\.\s)", text.strip())
    for block in blocks:
        m = re.match(r"^\s*\d+\.\s*(.+)$", block, flags=re.S)
        if not m:
            continue
        body = m.group(1).strip()
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        if not lines:
            continue
        title = lines[0]
        details = " ".join(lines[1:]).strip()
        if "," not in title:
            # enforce "City, Country"
            continue
        items.append({"title": title, "details": details})
    return items[:3]


def precheck_destinations(items: List[Dict[str, str]]) -> List[str]:
    issues: List[str] = []
    if len(items) != 3:
        issues.append("Did not produce exactly 3 destinations.")
        return issues
    cities = [it["title"].split(",")[0].strip().lower() for it in items]
    if len(set(cities)) < 3:
        issues.append("Duplicate city detected; ensure three distinct cities.")
    for it in items:
        if len(it.get("details", "").split()) < 5:
            issues.append("Justification too short/generic.")
            break
    return issues


def extract_json(s: str) -> str:
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found")
    return s[start : end + 1]


# ------------------------------------------------------------
# 5) Question Graph: generator → evaluator → (opt? → generator) → END
# ------------------------------------------------------------
def question_generator(state: State) -> Dict[str, Any]:
    info = state.get("info", "(none)")
    prompt = f"""You are a travel planning assistant.

Given the user's info:
{info}

Return a numbered list of up to 6 clarifying questions that—if answered—would most reduce uncertainty.
STRICT FORMAT:
- Use 1., 2., 3. numbering.
- Each line must be a single question ending with '?'.
- No preface or epilogue, only the list.
"""
    msg = llm.invoke(
        [
            SystemMessage(content="Clarifying question generator"),
            HumanMessage(content=prompt),
        ]
    )
    text = msg.content
    qs = parse_questions(text, max_n=6)
    return {
        "feedback": text,
        "question_queue": qs,
    }


def question_evaluator(state: State) -> Dict[str, Any]:
    info = state.get("info", "(none)")
    qs = state.get("question_queue", []) or []

    # fast precheck first (no LLM spend if clearly broken)
    issues = precheck_questions(qs)
    if issues:
        return {"qe_grade": "fail", "qe_notes": [f"Heuristic: {x}" for x in issues]}

    rubric = f"""Evaluate the clarifying questions for:
- Coverage of key unknowns (budget, travel window/season, vibe, flight-time tolerance, non-starters).
- Non-redundancy and answerability.
- Strict formatting (1. ...? lines, ≤6).

Reply in JSON ONLY:
{{"grade":"pass"|"fail","improvement_notes":["...","..."]}}

User info (context): {info}
Questions: {json.dumps(qs, ensure_ascii=False)}
"""
    msg = llm.invoke(
        [SystemMessage(content="Question evaluator"), HumanMessage(content=rubric)]
    )
    try:
        data = json.loads(extract_json(msg.content))
    except Exception:
        data = {"grade": "fail", "improvement_notes": ["Evaluator returned non-JSON."]}

    grade = "pass" if data.get("grade") == "pass" else "fail"
    notes = data.get("improvement_notes") or ["Be more specific, remove redundancy."]
    return {"qe_grade": grade, "qe_notes": notes}


def question_optimizer(state: State) -> Dict[str, Any]:
    it = (state.get("question_iteration") or 0) + 1
    notes = state.get("qe_notes", [])
    refinement = "- " + "\n- ".join(notes)
    # Nudge via info, so generator incorporates changes naturally
    new_info = (state.get("info") or "") + f"\nREFINEMENT_FOR_QUESTIONS:\n{refinement}"
    return {"question_iteration": it, "info": new_info}


def route_after_q_eval(state: State) -> str:
    if state.get("qe_grade") == "pass":
        return "end"
    if (state.get("question_iteration") or 0) < MAX_Q_ITERS:
        return "optimize"
    return "end"


def build_question_graph():
    g = StateGraph(State)
    g.add_node("question_generator", question_generator)
    g.add_node("question_evaluator", question_evaluator)
    g.add_node("question_optimizer", question_optimizer)

    g.set_entry_point("question_generator")
    g.add_edge("question_generator", "question_evaluator")
    g.add_conditional_edges(
        "question_evaluator",
        route_after_q_eval,
        {"optimize": "question_optimizer", "end": END},
    )
    g.add_edge("question_optimizer", "question_generator")
    return g.compile()


# ------------------------------------------------------------
# 6) Destination Graph: generator → evaluator → (opt? → generator) → END
# ------------------------------------------------------------
def destination_generator(state: State) -> Dict[str, Any]:
    info = state.get("info", "(none)")
    prompt = f"""You are a travel recommender.

User constraints and preferences:
{info}

Return exactly 3 options, numbered 1.-3.
Each option:
- First line: City, Country
- Next line(s): 1–2 sentences with specific neighborhoods/venues/seasonal hooks that match the constraints.

No pre/post text."""
    msg = llm.invoke(
        [SystemMessage(content="Destination generator"), HumanMessage(content=prompt)]
    )
    text = msg.content
    return {"destinations": text}


def destination_evaluator(state: State) -> Dict[str, Any]:
    raw = state.get("destinations", "") or ""
    items = parse_destinations(raw)

    # fast precheck
    issues = precheck_destinations(items)
    if issues:
        return {"dest_grade": "fail", "dest_notes": [f"Heuristic: {x}" for x in issues]}

    rubric = f"""Evaluate these 3 destination options for:
- Specificity (named neighborhoods/venues/seasonal timing).
- Fit to constraints in the user info.
- Diversity (not three near-identical options).

Reply in JSON ONLY:
{{"grade":"pass"|"fail","improvement_notes":["...","..."]}}

Candidates: {json.dumps(items, ensure_ascii=False)}
"""
    msg = llm.invoke(
        [SystemMessage(content="Destination evaluator"), HumanMessage(content=rubric)]
    )
    try:
        data = json.loads(extract_json(msg.content))
    except Exception:
        data = {"grade": "fail", "improvement_notes": ["Evaluator returned non-JSON."]}

    grade = "pass" if data.get("grade") == "pass" else "fail"
    notes = data.get("improvement_notes") or [
        "Increase specificity and align with constraints."
    ]
    return {"dest_grade": grade, "dest_notes": notes}


def destination_optimizer(state: State) -> Dict[str, Any]:
    it = (state.get("dest_iteration") or 0) + 1
    notes = state.get("dest_notes", [])
    refinement = "- " + "\n- ".join(notes)
    new_info = (
        state.get("info") or ""
    ) + f"\nREFINEMENT_FOR_DESTINATIONS:\n{refinement}"
    return {"dest_iteration": it, "info": new_info}


def route_after_dest_eval(state: State) -> str:
    if state.get("dest_grade") == "pass":
        return "end"
    if (state.get("dest_iteration") or 0) < MAX_DEST_ITERS:
        return "regen"
    return "end"


def build_destination_graph():
    g = StateGraph(State)
    g.add_node("destination_generator", destination_generator)
    g.add_node("destination_evaluator", destination_evaluator)
    g.add_node("destination_optimizer", destination_optimizer)

    g.set_entry_point("destination_generator")
    g.add_edge("destination_generator", "destination_evaluator")
    g.add_conditional_edges(
        "destination_evaluator",
        route_after_dest_eval,
        {"regen": "destination_optimizer", "end": END},
    )
    g.add_edge("destination_optimizer", "destination_generator")
    return g.compile()


# ------------------------------------------------------------
# 7) Public API (keeps your external Q&A loop style)
# ------------------------------------------------------------
class WorkflowManager:
    """
    Server-facing API:
      1) process_initial_message(info) -> state with high-quality question_queue
      2) get_next_question(state) -> str | None
      3) process_clarification_answer(state, answer) -> updated state (app owns loop)
      4) finalize_recommendations(state) -> dict with parsed destinations & notes
    """

    def __init__(self) -> None:
        self._q_runner = build_question_graph()
        self._d_runner = build_destination_graph()

    # Phase 1: prepare clarifying questions (eval + optional optimize)
    def process_initial_message(self, info: str) -> Dict[str, Any]:
        state: State = {
            "info": (info or "").strip(),
            "question_queue": [],
            "question_iteration": 0,
            "question_history": [],
        }
        state = self._q_runner(state)
        return dict(state)

    def get_next_question(self, state: Dict[str, Any]) -> Optional[str]:
        queue = state.get("question_queue") or []
        return queue[0] if queue else None

    def process_clarification_answer(
        self, state: Dict[str, Any], answer: str
    ) -> Dict[str, Any]:
        # Pop current question, append to history, and inline the Q/A into info (simple merge).
        queue = state.get("question_queue") or []
        if not queue:
            return state
        q = queue.pop(0)
        ans = (answer or "").strip()
        info = state.get("info") or ""
        info += f"\nQ: {q}\nA: {ans}"
        hist = state.get("question_history") or []
        hist.append({"q": q, "a": ans})
        state["info"] = info
        state["question_queue"] = queue
        state["question_history"] = hist
        return state

    # Phase 2: finalize with destination evaluator loop
    def finalize_recommendations(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if state.get("question_queue"):
            # let caller decide what to do if questions remain
            return {
                "error": "There are remaining clarifying questions. Finish them before finalizing.",
                "next_question": state["question_queue"][0],
            }
        state.setdefault("dest_iteration", 0)
        state = self._d_runner(state)

        raw = state.get("destinations", "") or ""
        items = parse_destinations(raw)
        notes = state.get("dest_notes") or []
        grade = state.get("dest_grade") or "fail"

        return {
            "grade": grade,
            "destinations": items,  # [{title, details}, ...]
            "notes": notes,  # evaluator/heuristic guidance
            "raw": raw,  # original text block (useful for logs)
            "iterations": state.get("dest_iteration", 0),
        }
