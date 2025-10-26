# ADR-002: LangGraph for Conversation Flow

## Context

We needed a way to manage multi-turn AI conversations for destination discovery where:
- User provides initial vacation preferences
- AI generates 3-6 clarifying questions
- User answers questions one-by-one across multiple HTTP requests
- AI generates exactly 3 destination recommendations
- State must persist between HTTP requests (users can close browser and resume)
- Django must control the Q&A loop (not the AI framework)

## Decision

We chose **LangGraph** (state machine framework) with this architecture:
- LangGraph defines the conversation workflow as a graph (nodes + edges)
- Django runs the graph ONCE to generate the question queue
- Django serves questions one-by-one, stores state in PostgreSQL
- When questions are exhausted, Django calls `destination_generator()` directly

## Why This Approach

### LangGraph vs. Plain LangChain

**Plain LangChain Pattern (rejected):**
```python
# Would require manual state management
def chat(user_message, session_id):
    history = load_from_db(session_id)
    response = llm.invoke(history + [user_message])
    save_to_db(session_id, response)
    return response
```

**Problems with plain LangChain:**
- ❌ No structured workflow (hard to enforce "ask 3-6 questions")
- ❌ Manual state management (we'd reinvent what LangGraph does)
- ❌ No pause/resume (would need custom logic)
- ❌ Testing harder (no node isolation)

**LangGraph Advantages:**
- ✅ Built-in state machine (define workflow as graph)
- ✅ Pause at any node, resume later (critical for our HTTP model)
- ✅ State persistence (TypedDict → JSON → PostgreSQL)
- ✅ Node isolation (test question generation separately from destinations)
- ✅ Conditional routing (if questions exist, stop; else, generate destinations)

---

### LangGraph vs. Custom Finite State Machine

**Alternative: Build our own FSM**
```python
class ConversationFSM:
    def __init__(self):
        self.state = "initial"

    def transition(self, event):
        if self.state == "initial" and event == "user_message":
            self.state = "generating_questions"
            return self.generate_questions()
        elif self.state == "asking_questions" and event == "answer":
            if self.questions_remaining():
                return self.next_question()
            else:
                self.state = "generating_destinations"
                return self.generate_destinations()
```

**Why we rejected custom FSM:**
- ❌ Reinventing the wheel (LangGraph does this better)
- ❌ No LangChain integration (would need manual LLM calls)
- ❌ Harder to extend (adding new nodes requires rewriting state transitions)
- ❌ No community support (we'd be sole maintainers)

**LangGraph wins because:**
- Pre-built state management
- Integrates with LangChain's LLM abstractions
- Visual graph representation (easy to understand workflow)
- Extensible (add nodes without breaking existing logic)

---

### LangGraph vs. DialogFlow / Rasa

**DialogFlow/Rasa = Intent-based chatbots**

**Why we rejected:**
- ❌ Overkill for our use case (designed for customer support, not vacation planning)
- ❌ Requires separate infrastructure (hosted service or server)
- ❌ Intent classification model (we don't have 100+ intents, just open-ended questions)
- ❌ Less flexible for our "freeform → clarification → generation" flow

**Our use case is NOT intent classification:**
- User doesn't say "book flight" or "cancel reservation" (predefined intents)
- User says "I want a relaxing vacation with good food" (open-ended)
- LLM generates custom questions based on user's unique input

---

### Hybrid Architecture: LangGraph + Django

**Key Design Decision**: Django controls the Q&A loop, NOT LangGraph.

**How It Works:**

1. **Initial Message** (User: "I want a beach vacation")
   ```
   Frontend → Django → LangGraph.invoke() → Gemini generates questions
                    → Django saves question_queue to DB
                    → Django returns first question
   ```

2. **Answer Questions** (User: "$3000")
   ```
   Frontend → Django → Load state from DB
                    → Append answer to user_info
                    → Pop question from queue
                    → Django returns next question
   ```

3. **Final Answer** (User: "July")
   ```
   Frontend → Django → Load state from DB
                    → Append answer, pop question
                    → Queue empty! → Call destination_generator() directly
                    → Django saves destinations
                    → Django returns destinations
   ```

**Why Django Controls Loop:**
- ✅ HTTP request/response model (one question per request)
- ✅ Rate limiting at Django level (protect Gemini API)
- ✅ Error handling in Django (catch LLM failures, return 500)
- ✅ User can close browser (state in DB, not memory)
- ✅ Simpler frontend (no WebSocket or polling needed)

**Alternative: LangGraph Controls Loop (rejected)**
```python
# This would require LangGraph to run across multiple HTTP requests
workflow.invoke({"info": "beach vacation"})  # Returns question 1
workflow.invoke({"follow_up": "$3000"})      # Returns question 2
# Problem: workflow.invoke() expects single execution, not stateful across calls
```

---

## Integration Impact

### Backend (Django)

**State Persistence** (`destination_search/models.py:46-98`):
```python
class ConversationState(models.Model):
    conversation = models.OneToOneField(TripConversation, on_delete=models.CASCADE)

    # LangGraph state → PostgreSQL
    user_info = models.TextField(default="")             # State['info']
    question_queue = models.JSONField(default=list)     # State['question_queue']
    destinations_text = models.TextField(default="")     # State['destinations']

    # Metadata
    current_stage = models.CharField(choices=WORKFLOW_STAGES)
    questions_asked = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
```

**View Integration** (`destination_search/views.py:92-107`):
```python
if conv_state.current_stage == "initial":
    # First message - start the workflow
    workflow_state = workflow_manager.process_initial_message(message_text)

    # Save to DB
    conv_state.user_info = workflow_state.get("info", "")
    conv_state.question_queue = workflow_state.get("question_queue", [])
    conv_state.total_questions = len(conv_state.question_queue)
    conv_state.current_stage = "asking_clarifications"
    conv_state.save()

    # Return first question
    ai_response_text = workflow_manager.get_next_question(workflow_state)
```

---

### LangGraph Workflow

**Graph Structure** (`recommendation_engine.py:169-192`):
```python
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
    route_clarifier,           # If questions exist → END, else → destination_generator
    {
        "destination_generator": "destination_generator",
        "end": END,
    },
)

workflow = builder.compile()
```

**Conditional Routing** (The Critical Part):
```python
def route_clarifier(state: State) -> str:
    """Stop graph if questions exist, let Django handle Q&A loop"""
    if state.get("question_queue"):
        return "end"  # Graph stops here, Django takes over
    return "destination_generator"  # No questions, generate destinations
```

---

### Frontend (React)

**Frontend is Unaware of LangGraph:**
- Just sends HTTP POST with user message
- Receives AI response (question or destinations)
- Updates UI based on `stage` field

**Frontend sees:**
```json
{
  "ai_message": { "content": "What's your budget?" },
  "stage": "asking_clarifications",
  "metadata": { "question_number": 1, "total_questions": 5 }
}
```

**Frontend doesn't know:**
- LangGraph generated the questions
- State is stored in PostgreSQL
- Questions were generated in bulk (frontend thinks AI is asking questions sequentially)

---

## Code References

**LangGraph Workflow:**
- `backend/destination_search/logic/recommendation_engine.py:169-192` - Graph definition
- `backend/destination_search/logic/recommendation_engine.py:108-115` - Conditional routing

**Django Integration:**
- `backend/destination_search/views.py:92-155` - Chat endpoint that runs workflow
- `backend/destination_search/models.py:46-98` - State persistence model

**WorkflowManager:**
- `recommendation_engine.py:198-262` - Django-facing API wrapper

---

## Future Considerations

### Streaming Responses

**Current**: User waits 2-5 seconds for full response.

**Future**: Stream LLM output token-by-token.

```python
# Using LangChain streaming callbacks
for chunk in llm.stream(prompt):
    yield chunk  # Send to frontend via WebSocket
```

**Requires:**
- WebSocket support (Django Channels)
- Frontend to handle incremental updates
- More complex state management

---

### Multi-Turn Refinement

**Current**: User gets 3 destinations, conversation ends.

**Future**: User can refine ("show me cheaper options").

**Solution**: Add a `refine` node after `destination_generator`:
```python
builder.add_node("refine", refine_destinations)
builder.add_conditional_edges(
    "destination_generator",
    detect_refinement_intent,
    {
        "refine": "refine",
        "end": END,
    },
)
```

---

### Branching Conversations

**Current**: Single conversation path (preferences → questions → destinations).

**Future**: User explores multiple vacation types in parallel.

**Solution**: LangGraph supports parallel execution:
```python
def split_by_type(state):
    return ["beach_workflow", "adventure_workflow", "culture_workflow"]

builder.add_conditional_edges("clarifier", split_by_type, {
    "beach_workflow": "beach_destination_generator",
    "adventure_workflow": "adventure_destination_generator",
    "culture_workflow": "culture_destination_generator",
})
```

---

## Lessons Learned

**What Worked Well:**
- Pause/resume across HTTP requests (critical for our use case)
- Node isolation made testing easy (mock LLM in tests, test each node separately)
- Conditional routing let Django control loop (best of both worlds)
- State persistence in PostgreSQL (users can resume conversations days later)

**What We'd Do Differently:**
- Use Pydantic structured output sooner (less text parsing)
- Add retry logic with exponential backoff for Gemini API failures
- Implement streaming responses from the start (better perceived performance)

**Unexpected Benefit:**
- Visual graph representation made onboarding new developers easier
- Easy to explain workflow: "Here's the graph, each node is a function, edges define flow"

**Biggest Challenge:**
- Integrating stateful workflow (LangGraph) with stateless protocol (HTTP)
- Solution: Hybrid architecture (graph generates roadmap, Django executes)

---

## Interview Talking Point

> "We use a hybrid LangGraph + Django architecture where LangGraph defines the conversation workflow as a state machine, but Django controls the HTTP request/response loop. This gives us the best of both worlds: powerful AI workflow orchestration and fine-grained control over the user experience.
>
> The key insight is that LangGraph runs ONCE to generate a question queue, then Django serves questions one-by-one across multiple HTTP requests. This allows users to close their browser mid-conversation and resume later because state is persisted in PostgreSQL, not kept in memory.
>
> We rejected plain LangChain because it would require reinventing LangGraph's state management, and we rejected DialogFlow because our use case is open-ended vacation planning, not intent classification."

---

**Related ADRs:**
- [ADR-001: Django REST Framework](./001-django-rest-framework-choices.md)
- [ADR-003: Gemini API Integration](./003-gemini-api-integration.md)
- [ADR-004: PostgreSQL Schema Design](./004-postgresql-schema-design.md)
