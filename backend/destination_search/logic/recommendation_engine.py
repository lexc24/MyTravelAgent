# destination_search/logic/recommendation_engine.py

import os
import re
from typing import List

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from typing_extensions import Literal, TypedDict

# ————————————————
# 1) LLM setup
# ————————————————
load_dotenv()
try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0
    )
except:
    llm = None  # Will be mocked in tests

# ————————————————
# 2) Feedback schema (kept for future use)
# ————————————————
class Feedback(BaseModel):
    grade: Literal["valid", "not valid"] = Field(
        description="Are these three destinations specific enough?"
    )
    feedback: str = Field(
        description="If not valid, ask exactly one follow-up question."
    )

evaluator = llm.with_structured_output(Feedback)

# ————————————————
# Helper: turn a numbered/bulleted blob into clean questions
# ————————————————
def extract_all_questions(text: str) -> List[str]:
    questions = []
    for line in text.splitlines():
        clean = re.sub(r'^[\s\-\*\d\.\)]+', '', line).strip()
        if clean.endswith('?'):
            questions.append(clean)
    # If nothing ends with '?', we return an empty list (no fallback injected)
    return questions

# ————————————————
# 3) Graph state
# ————————————————
class State(TypedDict, total=False):
    info: str                # accumulated user preferences
    follow_up: str           # last answer (not used in this Django flow)
    destinations: str        # the "three spots" text
    valid_or_not: str        # evaluator.grade
    feedback: str            # evaluator.feedback OR questions list text
    clarified_once: bool     # not used here, kept for parity
    question_queue: list[str]

# ————————————————
# 4) Nodes
# ————————————————
def ask_activities(state: State) -> dict:
    """Pass-through: in Django we already have initial info in state['info']."""
    return {"clarified_once": False}

def question_generator(state: State) -> dict:
    """Generate a compact numbered list of clarifying questions."""
    prompt = (
        f"I know the user likes: {state.get('info','')}\n"
        "Produce a numbered list of clarifying questions you need to fully pin down their dream vacation.\n"
        "Number them strictly as 1., 2., 3., … with each line ending in a question mark.\n"
        "Keep it concise and ask **no more than 6** questions."
    )
    msg = llm.invoke([
        SystemMessage(content="You are a travel-planning assistant."),
        HumanMessage(content=prompt),
    ])
    return {"feedback": msg.content}

def clarifier(state: State) -> dict:
    """
    Convert the feedback blob into a question_queue once, then hand control
    back to Django (we do NOT loop here).
    """
    if "question_queue" not in state:
        state["question_queue"] = extract_all_questions(state.get("feedback", "") or "")
    return state

def route_clarifier(state: State) -> str:
    """
    If there are questions to ask, stop the graph and let Django handle the Q/A loop.
    Otherwise proceed to destination generation.
    """
    if state.get("question_queue"):
        return "end"  # this label is mapped to END in add_conditional_edges
    return "destination_generator"

def destination_generator(state: State) -> dict:
    """
    Generate exactly three destinations in a parser-friendly format
    that your existing parse_destinations() can reliably split.
    """
    prompt = (
        f"Now that I know the user likes: {state.get('info','')}\n"
        "Return exactly THREE destinations as a numbered list 1., 2., 3.\n"
        "Each item must start with 'City, Country' on the first line,\n"
        "followed by 1–2 short lines describing why it fits.\n"
        "Do not include any text before or after the list."
    )
    msg = llm.invoke([
        SystemMessage(content="You are a travel-planning assistant."),
        HumanMessage(content=prompt),
    ])
    return {"destinations": msg.content}

# (Unused in this Django flow but kept for compatibility/debug)
def llm_call_generator(state: State) -> dict:
    prompt = (
        f"Based on: {state.get('info','')}"
        + (f" and {state.get('follow_up')}" if state.get("follow_up") else "")
        + "\nGive me three vacation spots."
    )
    msg = llm.invoke([
        SystemMessage(content="You are a travel-planning assistant."),
        HumanMessage(content=prompt),
    ])
    return {"destinations": msg.content}

def llm_call_evaluator(state: State) -> dict:
    check = (
        f"Here are three proposed destinations: {state.get('destinations','')}\n"
        f"Preferences: {state.get('info','')}"
        + (f" AND {state.get('follow_up')}" if state.get("follow_up") else "")
        + "\nAre these specific enough? If not, ask exactly one follow-up question."
    )
    grade = evaluator.invoke(check)
    return {"valid_or_not": grade.grade, "feedback": grade.feedback}

# ————————————————
# 5) Build the graph
# ————————————————
builder = StateGraph(State)
builder.add_node("ask_activities", ask_activities)
builder.add_node("question_generator", question_generator)
builder.add_node("clarifier", clarifier)
builder.add_node("destination_generator", destination_generator)

builder.add_edge(START, "ask_activities")
builder.add_edge("ask_activities", "question_generator")
builder.add_edge("question_generator", "clarifier")

builder.add_conditional_edges(
    "clarifier",
    route_clarifier,
    {
        "destination_generator": "destination_generator",
        "end": END,  # <- map the router's "end" label to END sentinel
    }
)

builder.add_edge("destination_generator", END)

optimizer_workflow = builder.compile()

# ————————————————
# 6) Django-facing wrapper
# ————————————————
class WorkflowManager:
    """
    Orchestrates the LangGraph workflow for Django integration.
    Django handles the Q/A loop; the graph only sets up the queue or produces final picks.
    """
    def __init__(self):
        self.workflow = optimizer_workflow

    def process_initial_message(self, user_message: str) -> dict:
        """
        Start the workflow with initial user preferences and build the question queue.
        (No fallback question injected here by design.)
        """
        state = {"info": user_message}
        result = self.workflow.invoke(state)

        # Build question queue from feedback and cap length
        questions = extract_all_questions(result.get("feedback", "") or "")
        result["question_queue"] = questions[:6]  # cap at 6 to keep UX tight
        return result

    def process_clarification_answer(self, current_state: dict, user_answer: str) -> dict:
        """
        Add the user's answer, pop the question, and either:
          - return updated state with remaining questions, or
          - generate final destinations when the queue is empty.
        """
        current_state["info"] = (current_state.get("info", "") + " " + user_answer).strip()

        if current_state.get("question_queue"):
            current_state["question_queue"].pop(0)

        if not current_state.get("question_queue"):
            # Directly generate final destinations (avoid re-running the whole graph)
            result = destination_generator(current_state)
            return {**current_state, **result}

        return current_state

    def get_next_question(self, state: dict) -> str | None:
        """Return the next question to ask, if any."""
        q = state.get("question_queue") or []
        return q[0] if q else None

    # (Optional) helpers to convert to/from DB storage
    def state_to_db_format(self, state: dict) -> dict:
        return {
            "user_info": state.get("info", ""),
            "question_queue": state.get("question_queue", []),
            "destinations_text": state.get("destinations", ""),
            "feedback": state.get("feedback", "")
        }

    def db_to_state_format(self, db_data: dict) -> dict:
        return {
            "info": db_data.get("user_info", ""),
            "question_queue": db_data.get("question_queue", []),
            "destinations": db_data.get("destinations_text", ""),
            "feedback": db_data.get("feedback", "")
        }
