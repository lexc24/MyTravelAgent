# ADR-003: Gemini API Integration

## Context

We needed an LLM provider for AI-powered destination recommendations with requirements:
- Generate clarifying questions based on user preferences
- Produce exactly 3 destination recommendations
- Fast response times (<3 seconds preferred)
- Cost-effective ($1-2 per 1000 user conversations)
- Reliable structured output (numbered lists, consistent formatting)
- Good at following instructions ("exactly 3 destinations", "numbered list")

## Decision

We chose **Google's Gemini API** (gemini-2.0-flash model) with:
- Temperature: 0 (deterministic)
- Integration via LangChain (`langchain-google-genai`)
- API key stored in environment variables
- Rate limiting at Django level (10 requests/min per user)

## Why This Approach

### Gemini vs. OpenAI GPT-4

**Cost Comparison:**

| Provider | Model | Cost per 1M tokens | Speed (avg) |
|----------|-------|-------------------|-------------|
| Google Gemini | gemini-2.0-flash | $0.15 | 1-2 seconds |
| OpenAI | gpt-4-turbo | $10.00 | 2-4 seconds |
| OpenAI | gpt-3.5-turbo | $0.50 | 1-2 seconds |

**Why Gemini Won:**
- ✅ **3x cheaper than gpt-3.5-turbo**, 67x cheaper than gpt-4-turbo
- ✅ **Fast**: gemini-2.0-flash optimized for low latency
- ✅ **Free tier**: $300 credit (enough for 2M tokens = 1000 conversations)
- ✅ **Structured output**: Good at following format instructions
- ✅ **Context window**: 32k tokens (enough for conversation history)

**Where GPT-4 Would Win:**
- ❌ More creative writing (but we want consistency, not creativity)
- ❌ Better at complex reasoning (our task is straightforward: questions → destinations)
- ❌ More widely tested (Gemini is newer, less community knowledge)

**Why We Accept Trade-offs:**
- Our use case is structured (generate questions, generate destinations)
- We use temperature=0 (deterministic), not creative writing
- Cost savings significant ($1 vs $10 per 1M tokens = 10x difference)

---

### Gemini vs. Claude (Anthropic)

**Comparison:**

| Feature | Gemini 2.0 Flash | Claude 3.5 Sonnet |
|---------|-----------------|-------------------|
| Cost | $0.15/1M tokens | $3.00/1M tokens |
| Speed | 1-2 seconds | 2-3 seconds |
| Free Tier | $300 credit | Limited free tier |
| Context Window | 32k tokens | 200k tokens |
| Structured Output | Good | Excellent |

**Why Gemini Won:**
- ✅ **20x cheaper** than Claude
- ✅ **Faster** (optimized for speed)
- ✅ **Better free tier** (enough for MVP + early users)

**Where Claude Would Win:**
- Claude is better at nuanced conversation, understanding context
- Larger context window (but we don't need 200k tokens)
- Better at avoiding hallucinations

**When We'd Reconsider:**
- If users want more nuanced, personalized recommendations
- If we add multi-day itinerary planning (need more context)
- If we can justify 20x higher costs

---

### Temperature: 0 (Deterministic)

**Configuration** (`recommendation_engine.py:18-26`):
```python
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0,  # Deterministic output
)
```

**Why Temperature 0:**
- ✅ **Consistent questions**: Same user input = same questions (easier to test)
- ✅ **Reliable formatting**: Less likely to deviate from "numbered list" instruction
- ✅ **Reproducible bugs**: If LLM generates bad output, we can reproduce it
- ✅ **Easier debugging**: Test cases don't randomly fail

**Where Higher Temperature Would Help:**
- Creative destination descriptions (temperature 0.7-0.9)
- Varied question phrasing (but we prefer consistency)
- More "human-like" responses (but users expect AI to be precise)

**Future**: Use temperature 0 for questions, temperature 0.7 for destination descriptions.

---

### API Key Management

**Security Strategy:**

1. **Development** (`.env` file, not committed):
   ```
   GOOGLE_API_KEY=AIzaSyC...
   ```

2. **Production** (Render environment variables):
   - Dashboard → Environment → Add Variable
   - Key: `GOOGLE_API_KEY`
   - Value: `AIzaSyC...` (from Google Cloud Console)

3. **Loading** (`recommendation_engine.py:17`):
   ```python
   from dotenv import load_dotenv
   load_dotenv()

   llm = ChatGoogleGenerativeAI(
       google_api_key=os.getenv("GOOGLE_API_KEY"),
       ...
   )
   ```

**Why This Pattern:**
- ✅ Never committed to Git (`.env` in `.gitignore`)
- ✅ Different keys for dev/prod (separate billing, easier to rotate)
- ✅ Easy to rotate (change env var, restart server)

**Security Risks:**
- ❌ If server compromised, attacker can read env vars
- ❌ If logs leak, API key might be exposed
- Future: Use secret management service (AWS Secrets Manager, Google Secret Manager)

---

## Integration Impact

### Prompt Engineering

**Question Generation Prompt** (`recommendation_engine.py:83-88`):
```python
prompt = (
    f"I know the user likes: {state.get('info','')}\n"
    "Produce a numbered list of clarifying questions you need to fully pin down their dream vacation.\n"
    "Number them strictly as 1., 2., 3., … with each line ending in a question mark.\n"
    "Keep it concise and ask **no more than 6** questions."
)
```

**Why This Works:**
- ✅ **Explicit format**: "numbered as 1., 2., 3." → easy to parse with regex
- ✅ **Question markers**: "ending in a question mark" → `extract_all_questions()` filters by `?`
- ✅ **Cap at 6**: Prevents LLM from asking 20 questions (bad UX)

**Alternative Prompts We Tried (and rejected):**
```python
# Too vague (LLM might not number)
"Generate some clarifying questions."

# Too strict (LLM might refuse)
"Generate EXACTLY 5 questions, no more, no less."

# Current (balanced)
"Ask no more than 6 questions"  # Gives LLM flexibility (3-6 questions)
```

---

**Destination Generation Prompt** (`recommendation_engine.py:123-129`):
```python
prompt = (
    f"Now that I know the user likes: {state.get('info','')}\n"
    "Return exactly THREE destinations as a numbered list 1., 2., 3.\n"
    "Each item must start with 'City, Country' on the first line,\n"
    "followed by 1–2 short lines describing why it fits.\n"
    "Do not include any text before or after the list."
)
```

**Why This Format:**
- ✅ **"City, Country"**: Easy to parse (split on comma)
- ✅ **"1–2 short lines"**: Prevents essays, keeps UI cards readable
- ✅ **"No text before or after"**: LLMs love preambles ("Here are three great destinations:"), this prevents that

**Example Output:**
```
1. Bali, Indonesia
Perfect luxury beach resort destination with world-class spas and restaurants. Great weather year-round.

2. Maldives
Ultimate luxury island experience with overwater bungalows. Crystal clear water, excellent diving.

3. Santorini, Greece
Beautiful beaches with upscale amenities, stunning sunsets, romantic atmosphere.
```

---

### Context Management

**How We Pass Context:**
```python
# We DON'T send full conversation history:
# messages = [
#     HumanMessage("I want a beach vacation"),
#     AIMessage("What's your budget?"),
#     HumanMessage("$3000"),
#     AIMessage("When?"),
#     ...
# ]

# We DO accumulate answers into a single string:
state['info'] = "I want a beach vacation. $3000. July. 7 days. Luxury hotels."

prompt = f"Based on: {state['info']}, return exactly three destinations."
```

**Why This Approach:**
- ✅ **Token-efficient**: One string vs 10+ message objects
- ✅ **Simpler**: No need to track message roles
- ✅ **Sufficient context**: LLM doesn't need exact conversation flow, just accumulated facts

**Where Full History Would Help:**
- If user contradicts themselves ("Actually, I hate beaches")
- If we add multi-turn refinement ("Show me cheaper options")
- For conversational memory (reference previous topics)

---

### Response Parsing

**Problem**: LLMs return text, we need structured data.

**Parsing Strategy** (`views.py:228-275`):

1. **Split by numbers**:
   ```python
   sections = re.split(r"\n(?=\d+\.|\n)", destinations_text)
   ```

2. **Extract name (first line)**:
   ```python
   lines = section.strip().split("\n")
   name = lines[0]  # "1. Bali, Indonesia"
   name = re.sub(r"^[\d\.\)\-\*\s]+", "", name)  # Remove "1. " → "Bali, Indonesia"
   ```

3. **Split city and country**:
   ```python
   if "," in name:
       parts = name.split(",")
       city = parts[0]  # "Bali"
       country = parts[1]  # "Indonesia"
   ```

4. **Extract description (remaining lines)**:
   ```python
   description = "\n".join(lines[1:])  # Everything after first line
   ```

5. **Fallback for errors**:
   ```python
   while len(destinations) < 3:
       destinations.append({
           "name": f"Option {len(destinations) + 1}",
           "country": "",
           "description": "Additional destination option",
       })
   ```

**Why This Parser is Resilient:**
- ✅ Handles inconsistent numbering ("1.", "1)", "- ", "* ")
- ✅ Always returns exactly 3 destinations (fills with placeholders if needed)
- ✅ Caps field lengths (name[:100], description[:500]) to prevent overflow

---

## Code References

**LLM Configuration:**
- `backend/destination_search/logic/recommendation_engine.py:18-26` - Gemini setup

**Prompt Engineering:**
- `recommendation_engine.py:83-95` - Question generation prompt
- `recommendation_engine.py:123-136` - Destination generation prompt

**Response Parsing:**
- `backend/destination_search/views.py:228-275` - `parse_destinations()` function

**Error Handling:**
- `views.py:220-225` - Catch LLM failures, return 500 error

---

## Future Considerations

### 1. Multiple LLM Providers (Fallback)

**Current**: If Gemini is down, entire chat feature breaks.

**Future**:
```python
providers = [
    ChatGoogleGenerativeAI(model="gemini-2.0-flash"),  # Primary
    ChatOpenAI(model="gpt-3.5-turbo"),                 # Fallback
]

for llm in providers:
    try:
        response = llm.invoke(prompt)
        break
    except Exception:
        continue  # Try next provider
```

**When to Implement:**
- If Gemini downtime becomes frequent
- If we hit rate limits (spread load across providers)

---

### 2. Structured Output (Pydantic)

**Current**: Text parsing with regex (brittle).

**Future**: Use LangChain structured output:
```python
from pydantic import BaseModel

class DestinationList(BaseModel):
    destinations: List[Destination]

class Destination(BaseModel):
    name: str
    country: str
    description: str

structured_llm = llm.with_structured_output(DestinationList)
result = structured_llm.invoke(prompt)
# result.destinations[0].name = "Bali"  # Guaranteed structure
```

**Benefits:**
- ✅ No parsing errors (guaranteed JSON)
- ✅ Type safety (Pydantic validation)
- ✅ Less code (no regex)

**When to Implement:**
- When we add more complex output (hotels, flights, activities)
- When parsing errors become frequent

---

### 3. Caching LLM Responses

**Current**: Every question regenerated (even if user input is identical).

**Future**:
```python
import hashlib

def cached_llm_invoke(prompt):
    cache_key = hashlib.md5(prompt.encode()).hexdigest()
    cached = redis.get(cache_key)

    if cached:
        return cached  # Return cached response

    response = llm.invoke(prompt)
    redis.set(cache_key, response, ex=3600)  # Cache for 1 hour
    return response
```

**Benefits:**
- ✅ Faster responses for common queries
- ✅ Reduced API costs

**Trade-off:**
- ❌ Need Redis instance
- ❌ Stale responses if prompts change

---

### 4. Streaming Responses

**Current**: User waits 2-5 seconds for full response.

**Future**: Stream LLM output token-by-token.

```python
for chunk in llm.stream(prompt):
    yield chunk  # Send to frontend via WebSocket
```

**Benefits:**
- ✅ Better perceived performance (user sees AI "typing")
- ✅ Can show progress (tokens received / estimated total)

**Requirements:**
- WebSocket support (Django Channels)
- Frontend to handle incremental updates

---

## Lessons Learned

**What Worked Well:**
- Gemini 2.0 Flash is fast enough (1-2 seconds) for real-time chat
- Temperature 0 makes testing easier (consistent output)
- Explicit format instructions ("numbered as 1., 2., 3.") work well
- Parser fallback (always return 3 destinations) prevents UI breaks

**What We'd Do Differently:**
- Use structured output (Pydantic) from the start (less regex)
- Add retry logic with exponential backoff for API failures (not implemented)
- Implement caching earlier (reduce costs, improve speed)
- Test with multiple LLM providers (don't lock into one)

**Biggest Surprise:**
- Gemini 2.0 Flash is comparable to gpt-3.5-turbo in quality
- Cost savings are significant ($0.15 vs $0.50 per 1M tokens = 3.3x cheaper)
- LLMs are good at following format instructions (with clear prompts)

---

## Interview Talking Point

> "We chose Gemini API over OpenAI because it's 3x cheaper than gpt-3.5-turbo and 67x cheaper than gpt-4-turbo, while being equally fast at 1-2 second response times. For our use case—generating structured questions and destinations—Gemini 2.0 Flash is sufficient. We use temperature 0 for deterministic output, which makes testing easier and ensures consistent question generation.
>
> Our prompt engineering focuses on explicit format instructions: 'Number them strictly as 1., 2., 3., with each line ending in a question mark.' This makes parsing reliable without needing structured output.
>
> If we were building a creative writing assistant or needed nuanced conversation, we'd consider Claude or GPT-4. But for structured task completion, Gemini is the pragmatic choice."

---

**Related ADRs:**
- [ADR-001: Django REST Framework](./001-django-rest-framework-choices.md)
- [ADR-002: LangGraph for Conversation Flow](./002-langgraph-for-conversation-flow.md)
- [ADR-004: PostgreSQL Schema Design](./004-postgresql-schema-design.md)
