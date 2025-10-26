# LangGraph Workflow Documentation

> **Status**: ✅ **FULLY IMPLEMENTED** - This is the core AI conversation engine powering the recommendation chat feature.

## Table of Contents
- [What is LangGraph and Why We Use It](#what-is-langgraph-and-why-we-use-it)
- [Workflow Architecture](#workflow-architecture)
- [State Management](#state-management)
- [Node Implementations](#node-implementations)
- [Integration with Gemini API](#integration-with-gemini-api)
- [Django Integration](#django-integration)
- [Conversation Flow Diagram](#conversation-flow-diagram)
- [Error Handling and Edge Cases](#error-handling-and-edge-cases)

---

## What is LangGraph and Why We Use It

### What is LangGraph?
LangGraph is a state machine framework built on top of LangChain that allows you to define complex, multi-step AI workflows as directed graphs. Each node in the graph represents a discrete operation (like calling an LLM or processing data), and edges define how data flows between nodes.

**Key Concepts:**
- **Nodes**: Functions that perform operations and return state updates
- **Edges**: Connections between nodes (conditional or direct)
- **State**: A TypedDict that persists data across the entire workflow
- **StateGraph**: The builder that compiles nodes and edges into an executable workflow

### Why LangGraph for MyTravelAgent?

We chose LangGraph over other approaches because of our specific conversation flow requirements:

**The Problem:**
- Users need to provide initial vacation preferences
- AI needs to ask 3-6 clarifying questions to narrow down destinations
- Django needs to handle the Q&A loop (not the graph)
- Finally, AI generates exactly 3 destination recommendations

**Alternatives Considered:**

1. **Plain LangChain Chains** ❌
   - Pro: Simpler, less boilerplate
   - Con: No built-in state management between API calls
   - Con: Would require manual session storage in Django
   - Why rejected: Can't pause/resume easily at arbitrary points

2. **Custom Finite State Machine** ❌
   - Pro: Full control, minimal dependencies
   - Con: Would duplicate what LangGraph already does well
   - Con: No integration with LangChain's LLM abstractions
   - Why rejected: Reinventing the wheel

3. **DialogFlow or Rasa** ❌
   - Pro: Purpose-built for conversational AI
   - Con: Heavyweight, requires separate infrastructure
   - Con: Overkill for our specific use case
   - Why rejected: We need flexibility for open-ended travel questions, not intent classification

**Why LangGraph Won:**
- **Pause/Resume**: Graph can stop at any node and resume later with persisted state
- **Django controls Q&A loop**: LangGraph generates the question queue, Django serves them one-by-one
- **State persistence**: Question queue and user info persist across HTTP requests
- **Testability**: Each node can be tested in isolation
- **Flexibility**: Easy to add new nodes (e.g., budget clarification, activity preferences)

**Trade-offs We Accepted:**
- Learning curve for team members unfamiliar with graph-based workflows
- Additional dependency (but LangChain was already decided for LLM abstraction)
- Slight over-engineering for current scope, but scales well for future features

---

## Workflow Architecture

### High-Level Graph Structure

```
START → ask_activities → question_generator → clarifier → [conditional routing] → destination_generator → END
                                                             |
                                                             └──> END (if questions exist)
```

### Node Responsibilities

| Node | Purpose | I/O |
|------|---------|-----|
| `ask_activities` | Pass-through initialization | Input: `info` (user message) → Output: `clarified_once: False` |
| `question_generator` | Generate 3-6 clarifying questions | Input: `info` → Output: `feedback` (numbered question list) |
| `clarifier` | Parse questions into queue | Input: `feedback` → Output: `question_queue` (list) |
| `destination_generator` | Generate 3 destinations | Input: `info` (accumulated) → Output: `destinations` (formatted text) |

**Key Design Decision**: The graph runs **once per stage**, not continuously. Django serves as the outer loop:
- Initial run: User provides preferences → Graph generates question queue → Graph STOPS at END
- Q&A loop: Django pops questions one-by-one, accumulates answers, stores in DB
- Final run: When queue is empty → Call `destination_generator()` directly → Get 3 destinations

This hybrid approach gives us:
- ✅ Stateful graph execution (LangGraph strength)
- ✅ HTTP request/response control (Django strength)
- ✅ Simple frontend UX (one message at a time, no polling)

---

## State Management

### State Schema

File: `backend/destination_search/logic/recommendation_engine.py:63-70`

```python
class State(TypedDict, total=False):
    info: str                 # Accumulated user preferences (grows with each answer)
    follow_up: str           # Last user answer (not used in Django flow)
    destinations: str        # Final 3 destinations text
    valid_or_not: str       # Evaluator grade (future use)
    feedback: str           # Raw LLM response with questions
    clarified_once: bool    # Flag (not used in this flow)
    question_queue: list[str]  # CRITICAL: List of questions to ask
```

**Most Important State Fields:**

1. **`info`** - The accumulating context string
   - Initially: User's first message ("I want a beach vacation")
   - After Q1: "I want a beach vacation. Budget is $3000"
   - After Q2: "I want a beach vacation. Budget is $3000. Traveling in July"
   - Used as context for final destination generation

2. **`question_queue`** - The conversation roadmap
   - Populated by `clarifier` node from LLM-generated questions
   - Capped at 6 questions max (`recommendation_engine.py:217`)
   - Django pops from front as each is answered
   - When empty → triggers destination generation

3. **`destinations`** - Final output
   - Structured text: "1. City, Country\nDescription..."
   - Parsed by `parse_destinations()` in `views.py:228-275`
   - Stored in `Recommendations` model as JSON

### State Persistence Strategy

**In-Memory (during graph execution):**
- LangGraph maintains state dict during `workflow.invoke()`
- State transitions between nodes automatically

**In Database (between HTTP requests):**

File: `backend/destination_search/models.py:46-84`

```python
class ConversationState(models.Model):
    conversation = models.OneToOneField(TripConversation, ...)

    # Workflow state tracking
    current_stage = models.CharField(choices=WORKFLOW_STAGES)  # e.g., "asking_clarifications"
    user_info = models.TextField()                             # Maps to State['info']
    question_queue = models.JSONField(default=list)           # Maps to State['question_queue']
    destinations_text = models.TextField()                     # Maps to State['destinations']

    # Progress metadata
    questions_asked = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
```

**Conversion Helpers** (`recommendation_engine.py:247-262`):

```python
def state_to_db_format(self, state: dict) -> dict:
    return {
        "user_info": state.get("info", ""),
        "question_queue": state.get("question_queue", []),
        "destinations_text": state.get("destinations", ""),
        "feedback": state.get("feedback", ""),
    }

def db_to_state_format(self, db_data: dict) -> dict:
    return {
        "info": db_data.get("user_info", ""),
        "question_queue": db_data.get("question_queue", []),
        "destinations": db_data.get("destinations_text", ""),
        "feedback": db_data.get("feedback", ""),
    }
```

---

## Node Implementations

### 1. `ask_activities` - Initialization Node

File: `recommendation_engine.py:76-78`

```python
def ask_activities(state: State) -> dict:
    """Pass-through: in Django we already have initial info in state['info']."""
    return {"clarified_once": False}
```

**Why it exists**: Originally designed for interactive prompting. Now just initializes flags. Could be removed in a refactor, but kept for graph structure clarity.

---

### 2. `question_generator` - LLM Question Generation

File: `recommendation_engine.py:81-95`

```python
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
```

**Interview-Worthy Insights:**

1. **Strict Formatting Requirements**
   - "Number them strictly as 1., 2., 3." - This makes parsing reliable
   - Each line must end with `?` - Regex extraction depends on this (`extract_all_questions()`)
   - Without strict formatting, we'd need complex NLP parsing or structured output

2. **Cap at 6 Questions**
   - Trade-off: More questions = better recommendations, but worse UX
   - 6 questions takes ~2-3 minutes to answer
   - Enforced again at `recommendation_engine.py:217` in case LLM ignores prompt

3. **Context Injection**
   - `state.get('info')` includes everything learned so far
   - LLM generates questions based on what it already knows
   - Example: If user said "beach", LLM won't ask "beach or mountains?"

---

### 3. `clarifier` - Question Parser

File: `recommendation_engine.py:98-105`

```python
def clarifier(state: State) -> dict:
    """
    Convert the feedback blob into a question_queue once, then hand control
    back to Django (we do NOT loop here).
    """
    if "question_queue" not in state:
        state["question_queue"] = extract_all_questions(state.get("feedback", "") or "")
    return state
```

**Helper Function** (`recommendation_engine.py:50-57`):

```python
def extract_all_questions(text: str) -> List[str]:
    questions = []
    for line in text.splitlines():
        clean = re.sub(r"^[\s\-\*\d\.\)]+", "", line).strip()  # Remove "1.", "- ", etc.
        if clean.endswith("?"):
            questions.append(clean)
    return questions
```

**Why This Design:**
- LLMs sometimes add preamble ("Here are some questions:") or formatting inconsistencies
- Regex extracts ONLY lines ending with `?`
- Strips bullets, numbers, and leading whitespace
- Returns empty list if LLM fails (handled by Django fallback logic)

**Edge Case Handling:**
- If LLM returns 0 questions → Django could generate a default question (not implemented)
- If LLM returns text without `?` → Empty queue → Skip to destinations immediately

---

### 4. `destination_generator` - Final Recommendations

File: `recommendation_engine.py:118-136`

```python
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
```

**Critical Prompt Engineering Decisions:**

1. **"Exactly THREE destinations"**
   - Prevents LLM from returning 5+ options (choice paralysis)
   - Parser expects exactly 3 (`parse_destinations()` fills missing ones with placeholders)

2. **"City, Country" format**
   - Comma-separated format enables easy parsing
   - Example: "Bali, Indonesia" → `name="Bali"`, `country="Indonesia"`
   - See parser: `views.py:252-255`

3. **"1–2 short lines describing why"**
   - Prevents LLM from writing essays
   - Keeps UI cards readable
   - Description extracted: `views.py:261`

4. **"Do not include any text before or after"**
   - LLMs love adding "Here are three great destinations:"
   - Removes need for preamble stripping in parser

---

### 5. `route_clarifier` - Conditional Routing

File: `recommendation_engine.py:108-115`

```python
def route_clarifier(state: State) -> str:
    """
    If there are questions to ask, stop the graph and let Django handle the Q/A loop.
    Otherwise proceed to destination generation.
    """
    if state.get("question_queue"):
        return "end"  # Maps to END sentinel - graph stops here
    return "destination_generator"  # Continue to final node
```

**Why This is Critical:**
- This is where the graph decides to pause or continue
- If questions exist → Return `"end"` → Graph exits → Django takes over
- If no questions → Go straight to `destination_generator`
- **This is the key integration point between LangGraph and Django**

**Graph Compilation** (`recommendation_engine.py:179-186`):

```python
builder.add_conditional_edges(
    "clarifier",
    route_clarifier,
    {
        "destination_generator": "destination_generator",
        "end": END,  # Maps router's "end" label to LangGraph's END sentinel
    },
)
```

---

## Integration with Gemini API

### LLM Configuration

File: `recommendation_engine.py:18-26`

```python
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0,
)
```

**Key Decisions:**

1. **Model: `gemini-2.0-flash`**
   - Fast (< 2s response time)
   - Cost-effective ($0.15 per 1M tokens)
   - Good at following structured instructions
   - Alternative considered: `gemini-2.0-pro` (more expensive, minimal quality gain for this use case)

2. **Temperature: 0** (Deterministic)
   - Ensures consistent question generation
   - Same user input = same questions (helpful for testing)
   - For creative writing (future feature), we'd use temperature 0.7

3. **API Key Management**
   - Loaded via `.env` file (not committed to repo)
   - Production: Set via Render environment variables
   - See `settings.py` for Django environment variable pattern

### Prompt Engineering Strategy

**System Message Pattern** (used in all nodes):
```python
[
    SystemMessage(content="You are a travel-planning assistant."),
    HumanMessage(content=prompt),
]
```

**Why This Works:**
- **Consistent persona**: "Travel-planning assistant" sets context for all responses
- **No chat history**: We inject accumulated `info` directly into prompts (simpler than message history)
- **Structured output**: Prompts explicitly request numbered lists, specific formats

**Context Management:**
- We DON'T send full conversation history to Gemini
- Instead, we accumulate user answers into `state['info']` string
- Example: `"I want a beach vacation. Budget is $3000. Traveling in July."`
- This is more token-efficient than sending 10 messages back and forth

### Response Parsing and Validation

**Parsing Destinations** (`views.py:228-275`):

```python
def parse_destinations(destinations_text):
    """
    Parse the AI-generated destinations text into structured data.
    Returns a list of destination dictionaries.
    """
    destinations = []

    # Split by numbers (1., 2., 3.) or double newlines
    sections = re.split(r"\n(?=\d+\.|\n)", destinations_text)

    for i, section in enumerate(sections[:3], 1):  # Take first 3
        if section.strip():
            lines = section.strip().split("\n")
            name = lines[0] if lines else f"Destination {i}"

            # Clean up: "1. Bali, Indonesia" → "Bali, Indonesia"
            name = re.sub(r"^[\d\.\)\-\*\s]+", "", name).strip()

            # Extract country: "Bali, Indonesia" → name="Bali", country="Indonesia"
            country = ""
            if "," in name:
                parts = name.split(",")
                name = parts[0].strip()
                country = parts[1].strip() if len(parts) > 1 else ""

            destinations.append({
                "name": name[:100],          # Limit to prevent overflow
                "country": country[:100],
                "description": "\n".join(lines[1:])[:500] if len(lines) > 1 else "",
            })

    # Ensure exactly 3 destinations (fill with placeholders if needed)
    while len(destinations) < 3:
        destinations.append({
            "name": f"Option {len(destinations) + 1}",
            "country": "",
            "description": "Additional destination option",
        })

    return destinations[:3]
```

**Why This Parser is Resilient:**
- Handles inconsistent LLM formatting (bullets, dashes, numbering)
- Extracts city/country from comma-separated format
- Falls back to "Option 1/2/3" if parsing fails
- Caps field lengths to prevent database overflow
- Always returns exactly 3 items (frontend expects this)

---

## Django Integration

### WorkflowManager Class

File: `recommendation_engine.py:198-262`

```python
class WorkflowManager:
    """
    Orchestrates the LangGraph workflow for Django integration.
    Django handles the Q/A loop; the graph only sets up the queue or produces final picks.
    """

    def __init__(self):
        self.workflow = optimizer_workflow  # Compiled LangGraph

    def process_initial_message(self, user_message: str) -> dict:
        """Start workflow with initial preferences and build question queue."""
        state = {"info": user_message}
        result = self.workflow.invoke(state)  # Runs graph until END

        questions = extract_all_questions(result.get("feedback", "") or "")
        result["question_queue"] = questions[:6]  # Cap at 6
        return result

    def process_clarification_answer(self, current_state: dict, user_answer: str) -> dict:
        """Add answer, pop question, generate destinations if queue is empty."""
        current_state["info"] = (current_state.get("info", "") + " " + user_answer).strip()

        if current_state.get("question_queue"):
            current_state["question_queue"].pop(0)  # Remove answered question

        if not current_state.get("question_queue"):
            # Queue empty → Generate destinations directly (bypass graph)
            result = destination_generator(current_state)
            return {**current_state, **result}

        return current_state

    def get_next_question(self, state: dict) -> str | None:
        """Return the next question to ask, if any."""
        q = state.get("question_queue") or []
        return q[0] if q else None
```

**Why This Design:**

1. **Single Responsibility**
   - `WorkflowManager` = Bridge between Django views and LangGraph
   - Views don't know about graph internals
   - Graph doesn't know about HTTP or database

2. **Django Controls Loop**
   - Graph runs ONCE to generate question queue
   - Django serves questions one-by-one via HTTP requests
   - Django accumulates answers and persists state in PostgreSQL
   - When queue is empty, Django calls `destination_generator()` directly

3. **Direct Destination Call**
   - `process_clarification_answer()` calls `destination_generator()` directly (line 237)
   - Bypasses full graph re-execution (performance optimization)
   - Works because `destination_generator()` only needs `state['info']`

### View Integration

File: `backend/destination_search/views.py:25-225`

**Initial Message Flow** (`views.py:92-107`):

```python
if conv_state.current_stage == "initial":
    # First message - start the workflow
    workflow_state = workflow_manager.process_initial_message(message_text)

    # Update conversation state in DB
    conv_state.user_info = workflow_state.get("info", "")
    conv_state.question_queue = workflow_state.get("question_queue", [])
    conv_state.total_questions = len(conv_state.question_queue)
    conv_state.current_stage = "asking_clarifications"
    conv_state.save()

    # Get first question
    ai_response_text = workflow_manager.get_next_question(workflow_state)
    if ai_response_text:
        conv_state.questions_asked = 1
        conv_state.save()
```

**Clarification Loop** (`views.py:109-155`):

```python
elif conv_state.current_stage == "asking_clarifications":
    # Reconstruct workflow state from DB
    current_state = workflow_manager.db_to_state_format({
        "user_info": conv_state.user_info,
        "question_queue": conv_state.question_queue,
        "destinations_text": conv_state.destinations_text,
        "feedback": "",
    })

    # Process the answer
    workflow_state = workflow_manager.process_clarification_answer(current_state, message_text)

    # Update DB
    conv_state.user_info = workflow_state.get("info", "")
    conv_state.question_queue = workflow_state.get("question_queue", [])

    # Check if we have destinations or more questions
    if workflow_state.get("destinations"):
        conv_state.destinations_text = workflow_state["destinations"]
        conv_state.current_stage = "destinations_complete"
        ai_response_text = workflow_state["destinations"]

        # Parse and save recommendations
        recommendations = Recommendations.objects.create(
            conversation=conversation,
            locations=parse_destinations(workflow_state["destinations"]),
        )
    else:
        # More questions to ask
        next_question = workflow_manager.get_next_question(workflow_state)
        if next_question:
            ai_response_text = next_question
            conv_state.questions_asked += 1

    conv_state.save()
```

**Key Integration Points:**

1. **Atomic Transactions** (`views.py:74`)
   - Entire conversation update wrapped in `transaction.atomic()`
   - Ensures message creation and state updates are all-or-nothing
   - Prevents orphaned messages if destination parsing fails

2. **Rate Limiting** (`views.py:27`)
   - `@ratelimit(key="user", rate="10/m")` - 10 requests per minute per user
   - Prevents abuse of expensive Gemini API calls
   - Returns HTTP 429 if exceeded

3. **User Isolation** (`views.py:67`)
   - `trip = get_object_or_404(Trip, id=trip_id, user=request.user)`
   - Users can only access their own trips
   - Prevents unauthorized access to other users' conversations

---

## Conversation Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INITIATES CHAT                         │
│                    "I want a beach vacation"                        │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DJANGO CHAT VIEW (views.py:28)                   │
│  • Validates input (SQL injection check)                            │
│  • Creates TripConversation & ConversationState                     │
│  • Saves user message to database                                   │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│               WORKFLOW MANAGER (Initial Message)                    │
│  workflow_manager.process_initial_message(user_message)             │
│                                                                     │
│     ┌─────────────────────────────────────────────────┐           │
│     │           LANGGRAPH EXECUTION                    │           │
│     │   START → ask_activities → question_generator    │           │
│     │        → clarifier → route_clarifier → END       │           │
│     └─────────────────────────────────────────────────┘           │
│                                                                     │
│  • Gemini generates 3-6 questions                                   │
│  • Parser extracts questions into list                              │
│  • Returns: { info, question_queue, feedback }                     │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   DJANGO SAVES STATE TO DB                          │
│  • ConversationState.user_info = "I want a beach vacation"         │
│  • ConversationState.question_queue = [Q1, Q2, Q3, Q4, Q5]        │
│  • ConversationState.current_stage = "asking_clarifications"       │
│  • ConversationState.total_questions = 5                            │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│             DJANGO RETURNS FIRST QUESTION TO USER                   │
│  AI: "What's your budget for this trip?"                            │
│  Metadata: { question_number: 1, total_questions: 5 }              │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
              ┌───────────┴────────────┐
              │   USER ANSWERS Q1      │
              │   "$3000"              │
              └───────────┬────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 DJANGO CHAT VIEW (Answer Flow)                      │
│  • Loads ConversationState from DB                                  │
│  • Calls process_clarification_answer(state, "$3000")              │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│            WORKFLOW MANAGER (Process Answer)                        │
│  • Appends answer to state['info']                                  │
│    info = "I want a beach vacation. $3000"                         │
│  • Pops first question from queue                                   │
│    question_queue = [Q2, Q3, Q4, Q5]                               │
│  • Checks if queue is empty → NO                                    │
│  • Returns updated state                                            │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  DJANGO SAVES & RETURNS Q2                          │
│  • Updates ConversationState.question_queue = [Q2, Q3, Q4, Q5]     │
│  • Increments questions_asked = 2                                   │
│  • Returns Q2: "When do you plan to travel?"                       │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
              ┌───────────┴────────────┐
              │  REPEAT FOR Q2-Q5      │
              └───────────┬────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│              USER ANSWERS Q5 (Final Question)                       │
│  "I want luxury accommodations"                                     │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│         WORKFLOW MANAGER (Final Answer Processing)                  │
│  • Appends final answer to state['info']                            │
│    info = "I want a beach vacation. $3000. July. 7 days. Luxury."  │
│  • Pops last question from queue                                    │
│    question_queue = []  ← EMPTY                                    │
│  • Detects empty queue → Calls destination_generator() directly     │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│            DESTINATION GENERATOR (Direct Call)                      │
│  • Calls Gemini with full accumulated context                       │
│  • Prompt: "Based on: [full info], return exactly 3 destinations"  │
│  • Gemini returns:                                                  │
│    1. Bali, Indonesia                                               │
│       Perfect luxury beach resort destination...                    │
│    2. Maldives                                                      │
│       Ultimate luxury island experience...                          │
│    3. Santorini, Greece                                             │
│       Beautiful beaches with upscale amenities...                   │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   DJANGO PARSES & STORES                            │
│  • parse_destinations() extracts structured data                    │
│  • Creates Recommendations model with JSON:                         │
│    [                                                                │
│      { name: "Bali", country: "Indonesia", description: "..." },   │
│      { name: "Maldives", country: "", description: "..." },        │
│      { name: "Santorini", country: "Greece", description: "..." }  │
│    ]                                                                │
│  • Updates ConversationState.current_stage = "destinations_complete"│
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│               DJANGO RETURNS TO FRONTEND                            │
│  • Response includes destinations JSON                              │
│  • Frontend displays 3 destination cards                            │
│  • User can select a destination or ask questions                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Error Handling and Edge Cases

### 1. LLM Failures

**Problem**: Gemini API could timeout, rate limit, or return malformed responses.

**Handling**:

```python
# recommendation_engine.py:18-26
try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0,
    )
except:
    llm = None  # Will be mocked in tests
```

**In Views** (`views.py:220-225`):
```python
except Exception as e:
    logger.error(f"Error in chat_message: {str(e)}", exc_info=True)
    return Response(
        {"error": "An error occurred processing your message"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
```

**Improvements Needed:**
- [ ] Retry logic with exponential backoff (not implemented)
- [ ] Fallback to default questions if question generation fails
- [ ] Cache recent LLM responses to avoid duplicate calls

### 2. Empty Question Queue

**Problem**: LLM might not generate any questions (no lines ending with `?`).

**Current Behavior**:
- `extract_all_questions()` returns `[]`
- `route_clarifier()` sees empty queue
- Graph skips directly to `destination_generator`
- User gets destinations after just one message

**Is This Acceptable?**
- ✅ **Yes** - If LLM feels confident, why ask unnecessary questions?
- ❌ **No** - Users might feel the AI didn't listen carefully

**Potential Fix**:
```python
# In views.py:101
if not conv_state.question_queue:
    # Generate a default question as fallback
    default_question = "What's your budget for this trip?"
    conv_state.question_queue = [default_question]
    conv_state.total_questions = 1
```

### 3. Malformed Destination Text

**Problem**: LLM returns destinations without proper formatting.

**Parser Resilience** (`views.py:265-273`):
```python
# Ensure exactly 3 destinations
while len(destinations) < 3:
    destinations.append({
        "name": f"Option {len(destinations) + 1}",
        "country": "",
        "description": "Additional destination option",
    })

return destinations[:3]
```

**Example Scenarios:**
- LLM returns 1 destination → Parser fills with "Option 2", "Option 3"
- LLM returns 5 destinations → Parser takes first 3
- LLM returns plain text (no numbers) → Parser returns 3 "Option X" placeholders

### 4. SQL Injection

**Problem**: User could input malicious SQL in chat messages.

**Defense** (`views.py:52-58`):
```python
try:
    validate_no_sql_injection(message_text)
except ValidationError as e:
    return Response(
        {"error": "Invalid input detected"},
        status=status.HTTP_400_BAD_REQUEST
    )
```

**Validator** (`api/validators.py` - not shown, but standard Django practice):
- Checks for `SELECT`, `DROP`, `INSERT`, `UPDATE`, `DELETE`, etc.
- Rejects messages containing SQL keywords
- Note: This is defense-in-depth; parameterized queries are the primary defense

### 5. Concurrent Requests

**Problem**: User rapidly clicks "Send" multiple times.

**Django Protection**:
- `transaction.atomic()` ensures one request completes before next starts
- Database row locking on `ConversationState` prevents race conditions

**Frontend Protection** (`RecommendationChat.jsx:536`):
```jsx
<Button
  onClick={sendMessage}
  disabled={!inputValue.trim() || isLoading || currentStage === "commitment_detected"}
/>
```

### 6. API Rate Limits

**Gemini Rate Limits** (as of 2025):
- Free tier: 15 requests/minute
- Paid tier: 1000 requests/minute

**Our Rate Limiting** (`views.py:27`):
```python
@ratelimit(key="user", rate="10/m", method="POST", block=False)
```

**Why 10/minute?**
- Typical conversation: 6 questions + 1 initial + 3 destination questions = ~10 messages
- Prevents abuse while allowing legitimate fast typing
- Per-user (not global), so doesn't block other users

---

## Future Enhancements

### 1. Streaming Responses
**Problem**: User waits 3-5s for LLM response with no feedback.

**Solution**: Use LangChain streaming callbacks
```python
llm.stream(prompt, callbacks=[StreamingCallback()])
```
Requires WebSocket integration or Server-Sent Events.

### 2. Multi-Turn Refinement
**Problem**: User gets 3 destinations but wants to refine (e.g., "show me cheaper options").

**Solution**: Add a `refine` node after `destination_generator`
- Detect refinement intent ("cheaper", "more adventurous", etc.)
- Re-run generator with modified constraints
- Update `Recommendations` with new options

### 3. Structured Output (Pydantic)
**Problem**: Parsing LLM text is brittle.

**Solution**: Use LangChain structured output
```python
class DestinationList(BaseModel):
    destinations: List[Destination]

structured_llm = llm.with_structured_output(DestinationList)
```
Guarantees JSON output, eliminates parsing errors.

### 4. Conversation Branching
**Problem**: User might want to explore multiple vacation types in parallel.

**Solution**: LangGraph supports branching workflows
- Add `split_by_type` node (beach, adventure, culture)
- Run 3 parallel destination generators
- Return 9 destinations (3 per category)

---

## Testing Strategy

### Unit Tests
**File**: `backend/destination_search/tests.py` (760+ LOC)

**Key Tests**:
1. `test_question_generator_formats_correctly()` - Ensures questions end with `?`
2. `test_destination_generator_returns_three()` - Validates exactly 3 destinations
3. `test_empty_question_queue_skips_to_destinations()` - Conditional routing
4. `test_parser_handles_malformed_text()` - Parser resilience

### Integration Tests
**File**: `backend/tests/integration_tests.py`

**Scenario**: Full conversation flow
1. Send initial message
2. Receive questions
3. Answer all questions
4. Receive destinations
5. Select destination
6. Verify trip updated

### Mocking Strategy
```python
# Mock LLM for faster tests
with patch('recommendation_engine.llm') as mock_llm:
    mock_llm.invoke.return_value.content = "1. Question 1?\n2. Question 2?"
    result = workflow_manager.process_initial_message("beach vacation")
    assert len(result['question_queue']) == 2
```

---

## Key Takeaways

**Why This Architecture Works:**
1. **Separation of Concerns**: LangGraph generates, Django orchestrates, PostgreSQL persists
2. **Pausable Workflows**: Graph stops at any node, Django handles HTTP in between
3. **Resilient Parsing**: Multiple fallbacks for LLM output variability
4. **User Control**: Django serves one question at a time (better UX than graph-driven loop)
5. **Stateful Without Sessions**: ConversationState in DB = no need for sticky sessions

**Interview Talking Points:**
- "We chose LangGraph because it lets us pause/resume AI workflows across HTTP requests without custom state management"
- "Django controls the Q&A loop, not the graph, because that gives us better UX control and error handling"
- "Temperature 0 for Gemini ensures consistent question generation, critical for testing"
- "Parser is intentionally over-engineered because LLMs are unpredictable - we handle 5+ failure modes"

**What I'd Do Differently:**
- Use Pydantic structured output instead of text parsing (less brittle)
- Add streaming for better perceived performance
- Implement retry logic with exponential backoff for Gemini API
- Add conversation branching for exploring multiple vacation types

---

**Related Documentation:**
- [API_DESIGN.md](./API_DESIGN.md) - Chat endpoint details
- [BACKEND_DESIGN.md](./BACKEND_DESIGN.md) - Django views implementation
- [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - ConversationState model
- [ADR 002: LangGraph Choice](./adr/002-langgraph-for-conversation-flow.md) - Decision rationale
- [ADR 003: Gemini API](./adr/003-gemini-api-integration.md) - LLM provider choice
