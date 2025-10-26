# ADR-001: Django REST Framework Choices

## Context

We needed to choose a backend framework for MyTravelAgent that could:
- Provide RESTful API endpoints for the React frontend
- Handle authentication (JWT tokens)
- Integrate with AI libraries (LangChain, LangGraph)
- Support rapid development with good documentation
- Scale for future features (payments, real-time updates)

## Decision

We chose **Django 4.2 + Django REST Framework 3.16** with the following patterns:
- ViewSets for automatic CRUD endpoints
- JWT token-based authentication (djangorestframework-simplejwt)
- Nested serializers for related data
- Rate limiting via django-ratelimit
- PostgreSQL via Django ORM

## Why This Approach

### Django REST Framework vs. FastAPI

**Pros of DRF:**
- ✅ Mature ecosystem (10+ years, battle-tested)
- ✅ Django ORM (better than SQLAlchemy for our use case)
- ✅ Built-in admin panel (manage destinations, users without custom UI)
- ✅ Extensive third-party packages (JWT, filters, CORS)
- ✅ Team expertise (faster onboarding)

**Cons of DRF (trade-offs):**
- ❌ Slower than FastAPI (Django is synchronous, FastAPI is async)
- ❌ More boilerplate (serializers, viewsets vs. Pydantic models)
- ❌ Older async support (async views added in Django 4.1, but limited)

**Why we accepted the trade-offs:**
- Our bottleneck is LLM API calls (2-5s), not Django request handling (<100ms)
- Django admin panel saves weeks of building admin UI
- Mature ecosystem reduces risk (well-documented, StackOverflow answers)

### Django REST Framework vs. Plain Django

**Why DRF over plain Django views:**
- ViewSets auto-generate CRUD endpoints (less code)
- Serializers handle JSON validation and transformation (safer than manual parsing)
- Built-in authentication classes (JWT, session, token)
- Pagination, filtering, ordering built-in
- OpenAPI schema generation (future: auto-generate API docs)

**Alternative we rejected:**
```python
# Plain Django view (verbose)
def get_trips(request):
    if request.method == "GET":
        trips = Trip.objects.filter(user=request.user)
        data = [{"id": t.id, "title": t.title, ...} for t in trips]
        return JsonResponse({"trips": data})

# DRF ViewSet (concise)
class TripViewSet(viewsets.ModelViewSet):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    permission_classes = [IsAuthenticated]
```

### ViewSets vs. APIView

**Decision**: Use ViewSets for standard CRUD, APIView for custom logic.

**ViewSets** (`api/views.py:63-106`):
- Automatic endpoints: list, create, retrieve, update, destroy
- Less code, standard patterns
- Used for: Trips, UserPreferences, PlanningSession, Destinations

**APIView / Function-Based Views** (`destination_search/views.py:25-457`):
- Custom logic (AI chat endpoint doesn't fit CRUD)
- Complex state management (LangGraph integration)
- Used for: Chat messages, conversation reset

### Authentication Strategy: JWT

**Decision**: JWT tokens (not session-based auth).

**Why JWT:**
- ✅ Stateless (no server-side session storage needed)
- ✅ Scales horizontally (no sticky sessions)
- ✅ Mobile-friendly (easy to store in apps)
- ✅ Standard (RFC 7519)

**Configuration** (`settings.py:161-166`):
```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),  # Short-lived
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),     # Long-lived
    "ROTATE_REFRESH_TOKENS": True,                   # Security
    "BLACKLIST_AFTER_ROTATION": True,                # Prevent reuse
}
```

**Alternatives considered:**
- **Session-based auth**: ❌ Requires sticky sessions, harder to scale
- **OAuth2**: ❌ Overkill for our use case (no third-party apps)
- **API keys**: ❌ No user context, can't be revoked easily

## Integration Impact

### Backend (Django)
- All API views protected by `@permission_classes([IsAuthenticated])`
- User extracted from JWT token: `request.user`
- Rate limiting per user: `@ratelimit(key="user", rate="10/m")`

### Frontend (React)
- Stores access + refresh tokens in localStorage
- Axios interceptor injects `Authorization: Bearer {token}` header
- Token expires → User must refresh or re-login

### Database
- Django ORM generates SQL migrations automatically
- PostgreSQL-specific features available (JSONField, full-text search)

## Code References

**ViewSet Example:**
- `backend/api/views.py:63-106` - TripViewSet with filtering, pagination, rate limiting

**Serializer Pattern:**
- `backend/api/serializers.py:91-112` - TripListSerializer with nested destination

**JWT Authentication:**
- `backend/backend/settings.py:150-166` - REST_FRAMEWORK + SIMPLE_JWT config
- `frontend/src/api.js:10-21` - Axios interceptor for token injection

**Custom View:**
- `backend/destination_search/views.py:28-225` - Complex chat endpoint (doesn't fit ViewSet pattern)

## Future Considerations

### Potential Changes

1. **Async Django Views** (Django 5.0+)
   - Current: Synchronous views (one request blocks thread)
   - Future: `async def chat_message(request)` for concurrent LLM calls
   - Benefit: Handle more requests per server instance

2. **GraphQL Layer** (Optional)
   - Current: REST API (over-fetching in some cases)
   - Future: Add Graphene-Django for flexible queries
   - Benefit: Frontend requests only needed fields
   - Trade-off: Adds complexity, caching harder

3. **WebSocket Support** (for real-time features)
   - Current: HTTP polling for chat messages
   - Future: Django Channels for WebSocket support
   - Benefit: Real-time AI streaming responses
   - Use case: Show LLM typing indicator, stream destinations as they generate

4. **API Versioning**
   - Current: No versioning (all endpoints are implicit v1)
   - Future: `/api/v1/trips/`, `/api/v2/trips/`
   - When: Breaking changes needed (e.g., change response format)

### When to Reconsider

**Migrate to FastAPI if:**
- LLM API calls become non-blocking (need async/await everywhere)
- Handling 10,000+ concurrent users (FastAPI's async is faster)
- Team expertise shifts to FastAPI

**Stick with Django if:**
- Admin panel remains critical (FastAPI has no equivalent)
- Team prefers Django's "batteries-included" philosophy
- Performance is acceptable (current bottleneck is LLM, not Django)

## Lessons Learned

**What Worked Well:**
- ViewSets reduced boilerplate (auto CRUD endpoints)
- Django admin panel saved weeks of building admin UI
- Django ORM migrations are smooth (no manual SQL)
- JWT tokens enable horizontal scaling (no session affinity needed)

**What We'd Do Differently:**
- Consider FastAPI earlier if we knew async would be critical
- Implement automatic token refresh on frontend sooner (UX issue)
- Use Pydantic for LangGraph state validation from the start (added later)

**Interview Talking Point:**
> "We chose Django REST Framework over FastAPI because our bottleneck is the Gemini API (2-5 second response times), not Django's request handling. DRF's mature ecosystem, built-in admin panel, and team expertise made it the pragmatic choice. If we were building a real-time trading platform with thousands of concurrent WebSocket connections, FastAPI would be better. For our use case, DRF is the right tool."

---

**Related ADRs:**
- [ADR-002: LangGraph for Conversation Flow](./002-langgraph-for-conversation-flow.md)
- [ADR-003: Gemini API Integration](./003-gemini-api-integration.md)
- [ADR-004: PostgreSQL Schema Design](./004-postgresql-schema-design.md)
