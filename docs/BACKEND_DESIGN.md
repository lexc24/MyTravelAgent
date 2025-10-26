# Backend Design Documentation

> **Framework**: Django 4.2 + Django REST Framework 3.16 | **Language**: Python 3.11 | **Status**: ✅ Core complete

## Overview

This document covers all Django backend files, design patterns, and integration points with the frontend and AI systems.

## Table of Contents
- [Django Project Structure](#django-project-structure)
- [Settings and Configuration](#settings-and-configuration)
- [URL Routing](#url-routing)
- [Models Deep Dive](#models-deep-dive)
- [Serializers](#serializers)
- [Views and ViewSets](#views-and-viewsets)
- [Custom Decorators and Validators](#custom-decorators-and-validators)
- [Testing Strategy](#testing-strategy)

---

## Django Project Structure

```
backend/
├── manage.py                      # Django CLI entry point
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Production container image
│
├── backend/                       # Project configuration
│   ├── settings.py               # Core settings (263 LOC) ⭐
│   ├── urls.py                   # Root URL routing
│   ├── wsgi.py                   # Production WSGI server
│   ├── asgi.py                   # ASGI (future WebSocket support)
│   └── tests.py                  # Integration tests
│
├── api/                          # Trip management app
│   ├── models.py                 # Trip, Destination, UserPreferences
│   ├── views.py                  # REST API ViewSets
│   ├── serializers.py            # DRF serializers
│   ├── urls.py                   # API routing
│   ├── validators.py             # Input validation
│   ├── decorators.py             # Custom decorators
│   ├── admin.py                  # Django admin config
│   ├── tests.py                  # Unit tests
│   └── migrations/               # Database schema versions
│
├── destination_search/           # AI recommendation app
│   ├── logic/
│   │   └── recommendation_engine.py  # LangGraph workflow (263 LOC) ⭐
│   ├── models.py                 # Conversation, Message, State
│   ├── views.py                  # Chat API endpoints (457 LOC) ⭐
│   ├── serializers.py            # Conversation serializers
│   ├── urls.py                   # Chat routing
│   ├── admin.py                  # Admin interface
│   ├── tests.py                  # AI workflow tests (760+ LOC)
│   └── migrations/               # Schema for conversations
│
└── tests/                        # Additional test suites
    ├── integration_tests.py      # Full stack tests
    ├── environment_tests.py      # Environment validation
    └── performance_tests.py      # Performance benchmarks
```

---

## Settings and Configuration

File: `backend/backend/settings.py` (263 lines)

### Environment Detection

```python
# settings.py:43
DEBUG = os.environ.get("DEBUG", "False").lower() in ["true", "1", "yes", "on"]

# settings.py:46-49
if DEBUG:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
else:
    ALLOWED_HOSTS = [".onrender.com", "localhost"]
```

**Why This Pattern:**
- Environment variable controls debug mode (secure default: off)
- Production automatically allows Render subdomains
- Localhost always allowed (for admin access)

---

### Database Configuration with Fallback

```python
# settings.py:106-119
if os.environ.get("DATABASE_URL"):
    # Production: Neon DB (dj-database-url parses connection string)
    DATABASES = {"default": dj_database_url.parse(os.environ.get("DATABASE_URL"))}
else:
    # Development: Docker Postgres
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "travel_DB"),
            "USER": os.environ.get("DB_USER", "lexc"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "secretpassw0rd"),
            "HOST": os.environ.get("DB_HOST", "db"),  # Docker service name
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
```

**Design Decision**: One environment variable (`DATABASE_URL`) switches between dev and prod databases. No code changes needed.

---

### Middleware Order

```python
# settings.py:68-78
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",    # MUST be first for CORS preflight
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Static files in production
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
```

**Order Matters**: CORS must run before SecurityMiddleware to handle preflight OPTIONS requests.

---

### JWT Configuration

```python
# settings.py:161-166
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),      # Short for security
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),         # Long for UX
    "ROTATE_REFRESH_TOKENS": not DEBUG,                  # Prod only (avoid dev annoyance)
    "BLACKLIST_AFTER_ROTATION": not DEBUG,               # Prevent token reuse
}
```

**Interview Insight**: "We rotate refresh tokens only in production to prevent dev friction while maintaining security in prod."

---

### CORS Configuration by Environment

```python
# settings.py:172-186
if DEBUG:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:5173",    # Vite dev server
        "http://127.0.0.1:5173",
    ]
else:
    CORS_ALLOWED_ORIGINS = [
        "https://my-travel-agent.onrender.com",  # Production frontend
    ]
```

**Security**: Explicit whitelist prevents other sites from calling our API.

---

### Logging Configuration

```python
# settings.py:250-261
"loggers": {
    "destination_search": {
        "handlers": ["console"],
        "level": "DEBUG" if DEBUG else "INFO",    # Verbose logs in dev
        "propagate": False,
    },
}
```

**Usage in Views:**
```python
logger = logging.getLogger(__name__)
logger.error(f"Error in chat_message: {str(e)}", exc_info=True)  # Full traceback
```

---

## URL Routing

### Root URLs

File: `backend/backend/urls.py`

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/user/register", CreateUserView.as_view(), name="register"),
    path("api/token", TokenObtainPairView.as_view(), name="get_token"),
    path("api/token/refresh", TokenRefreshView.as_view(), name="refresh"),
    path("api/", include("api.urls")),                    # Trip management endpoints
    path("api-auth/", include("rest_framework.urls")),
    path("health", lambda request: HttpResponse("OK")),   # Health check for Render
    path("destination_search/", include("destination_search.urls")),  # Chat endpoints
]
```

**Design Decision**: No trailing slashes (`APPEND_SLASH = False` in settings).
- **Why**: Frontend uses `/api/trips/` (with slash), `/api/token` (no slash)
- Consistency: Decided no trailing slashes for auth endpoints, maintain across API

---

### API App URLs (DRF Router)

File: `backend/api/urls.py`

```python
router = DefaultRouter()
router.register(r"trips", TripViewSet, basename="trip")
router.register(r"user-preferences", UserPreferencesViewSet, basename="userpreferences")
router.register(r"planning-sessions", PlanningSessionViewSet, basename="planningsession")
router.register(r"destinations", DestinationViewSet, basename="destination")

urlpatterns = router.urls
```

**Auto-Generated Endpoints:**
- `GET /api/trips/` → `TripViewSet.list()`
- `POST /api/trips/` → `TripViewSet.create()`
- `GET /api/trips/{id}/` → `TripViewSet.retrieve()`
- `PATCH /api/trips/{id}/` → `TripViewSet.partial_update()`
- `DELETE /api/trips/{id}/` → `TripViewSet.destroy()`
- `POST /api/planning-sessions/{id}/advance_stage/` → Custom action

---

### Destination Search URLs

File: `backend/destination_search/urls.py`

```python
urlpatterns = [
    path("chat/", chat_message, name="chat_message"),
    path("conversations/<int:trip_id>/", get_conversation, name="get_conversation"),
    path("conversations/<int:trip_id>/reset/", reset_conversation, name="reset_conversation"),
]
```

**Function-Based Views** (not ViewSets) for custom logic.

---

## Models Deep Dive

See [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) for complete model documentation.

**Key Models:**
- `User` (Django built-in) - Authentication
- `UserPreferences` (OneToOne User) - AI-discovered preferences
- `Trip` (ForeignKey User) - Main planning entity
- `Destination` - Destination catalog
- `TripConversation` (OneToOne Trip) - Chat session
- `Message` (ForeignKey Conversation) - Chat history
- `ConversationState` (OneToOne Conversation) - **LangGraph state persistence**
- `Recommendations` (ForeignKey Conversation) - Generated destinations (JSON)

---

## Serializers

### Dynamic Serializer Selection

File: `backend/api/views.py:78-84`

```python
def get_serializer_class(self):
    """Use different serializers for different actions"""
    if self.action == "list":
        return TripListSerializer          # Lightweight for list views
    elif self.action in ["create", "update", "partial_update"]:
        return TripCreateUpdateSerializer  # Validation for writes
    return TripDetailSerializer            # Full details for single item
```

**Why**: Optimize payload size (list view doesn't need full user details, description, etc.)

---

### Nested Serialization

File: `backend/api/serializers.py:91-112`

```python
class TripListSerializer(serializers.ModelSerializer):
    destination = DestinationSerializer(read_only=True)  # Nested object
    duration_days = serializers.ReadOnlyField()          # Computed property

    class Meta:
        model = Trip
        fields = [
            "id", "title", "destination", "start_date", "end_date",
            "budget", "status", "travelers_count", "duration_days",
            "created_at", "updated_at",
        ]
```

**Result:**
```json
{
  "id": 10,
  "destination": {
    "id": 3,
    "name": "Bali",
    "country": "Indonesia",
    "description": "..."
  },
  "duration_days": 8
}
```

**Alternative (ID only)**:
```python
fields = ["id", "title", "destination", ...]  # destination would be integer (FK)
```

**Trade-off**: Nested = fewer HTTP requests, but larger payload. We chose nested for better UX.

---

### Validation

File: `backend/api/serializers.py:156-164`

```python
def validate(self, data):
    """Validate trip dates"""
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if start_date and end_date and start_date >= end_date:
        raise serializers.ValidationError("End date must be after start date")

    return data
```

**DRF calls this automatically during `serializer.is_valid()`.**

---

### Auto-Create Related Models

File: `backend/api/serializers.py:32-37`

```python
def create(self, validated_data):
    """Create user and associated preferences"""
    user = User.objects.create_user(**validated_data)  # Hashes password
    # Auto-create UserPreferences when user registers
    UserPreferences.objects.create(user=user)
    return user
```

**Why**: Ensures every user has a preferences object (no null checks needed).

---

## Views and ViewSets

### Trip Management ViewSet

File: `backend/api/views.py:63-106`

```python
class TripViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = TripPagination           # 10 items per page
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "destination"]
    ordering_fields = ["created_at", "start_date", "title"]
    ordering = ["-created_at"]                  # Default: newest first

    def get_queryset(self):
        """Only return trips for the authenticated user"""
        return Trip.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Set the trip owner to the current user"""
        serializer.save(user=self.request.user)
```

**Key Patterns:**

1. **User Isolation** (`get_queryset`)
   - Every query filtered by `user=request.user`
   - Impossible to access other users' trips

2. **Automatic User Assignment** (`perform_create`)
   - User doesn't send `user_id` in request body
   - Backend extracts from JWT and assigns

3. **Rate Limiting**
   ```python
   @method_decorator(ratelimit(key="user", rate="100/h", method="GET", block=True))
   def list(self, request, *args, **kwargs):
       if getattr(request, "limited", False):
           return Response({"error": "Rate limit exceeded"}, 429)
       return super().list(request, *args, **kwargs)
   ```

---

### Chat Message Endpoint (Complex)

File: `backend/destination_search/views.py:28-225` (198 lines!)

**Flow:**

1. **Validate Input** (lines 47-64)
   ```python
   trip_id = request.data.get("trip_id")
   message_text = request.data.get("message", "").strip()

   # SQL injection check
   validate_no_sql_injection(message_text)

   # Verify trip ownership
   trip = get_object_or_404(Trip, id=trip_id, user=request.user)
   ```

2. **Get/Create Conversation & State** (lines 76-81)
   ```python
   with transaction.atomic():
       conversation, created = TripConversation.objects.get_or_create(trip=trip)
       conv_state, state_created = ConversationState.objects.get_or_create(
           conversation=conversation, defaults={"current_stage": "initial"}
       )
   ```

3. **Route Based on Stage** (lines 88-169)
   ```python
   if conv_state.current_stage == "initial":
       # First message - run LangGraph workflow
       workflow_state = workflow_manager.process_initial_message(message_text)
       # Save question queue to DB
       conv_state.question_queue = workflow_state.get("question_queue", [])
       # Return first question

   elif conv_state.current_stage == "asking_clarifications":
       # Process answer
       workflow_state = workflow_manager.process_clarification_answer(current_state, message_text)
       # Check if destinations generated or more questions

   elif conv_state.current_stage == "destinations_complete":
       # Handle post-destination messages (commitment detection)
   ```

4. **Save Messages & Return Response** (lines 171-213)

**Why So Complex?**
- Handles 3 different conversation stages
- Integrates with LangGraph workflow
- Parses and stores AI responses
- Updates trip status
- Returns structured JSON with metadata

---

### Planning Session Custom Actions

File: `backend/api/views.py:140-168`

```python
@action(detail=True, methods=["post"])
def advance_stage(self, request, pk=None):
    """Move to the next planning stage"""
    session = self.get_object()

    old_stage = session.current_stage
    next_stage = session.get_next_stage()

    if next_stage == "completed":
        session.current_stage = "completed"
        session.is_active = False
        session.completed_at = timezone.now()
    else:
        session.current_stage = next_stage

    session.mark_stage_completed(old_stage)
    session.save()

    return Response({
        "previous_stage": old_stage,
        "current_stage": session.current_stage,
        "is_complete": session.current_stage == "completed",
    })
```

**Custom Action** = endpoint beyond CRUD: `POST /api/planning-sessions/{id}/advance_stage/`

---

## Custom Decorators and Validators

### SQL Injection Validator

File: `backend/api/validators.py` (not shown in reads, but referenced)

```python
def validate_no_sql_injection(text):
    """Check for SQL injection patterns"""
    dangerous_patterns = [
        "SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
        "EXEC", "EXECUTE", "--", "/*", "*/", "xp_", "sp_", "UNION",
    ]

    text_upper = text.upper()
    for pattern in dangerous_patterns:
        if pattern in text_upper:
            raise ValidationError(f"Invalid input detected: {pattern}")
```

**Why Needed?**
- Chat messages are user-controlled text
- Django ORM prevents SQL injection, but defense-in-depth principle
- Rejects messages like "'; DROP TABLE users; --"

**Limitation**: False positives (user might legitimately type "I want to DROP by the beach").
**Future**: Use context-aware NLP-based detection instead of keyword matching.

---

### Rate Limit Decorator

File: `backend/api/decorators.py` (not shown, but pattern visible in views)

```python
@method_decorator(
    ratelimit(key="user", rate="10/m", method="POST", block=True),
    name="create"
)
```

**Keys:**
- `"user"` - Per authenticated user
- `"ip"` - Per IP address (for public endpoints like registration)
- `"user_or_ip"` - Use user if authenticated, else IP

---

## Testing Strategy

### Unit Tests

File: `backend/destination_search/tests.py` (760+ LOC)

**Key Test Categories:**

1. **LangGraph Workflow Tests**
   ```python
   def test_process_initial_message_generates_questions(self):
       workflow = WorkflowManager()
       result = workflow.process_initial_message("I want a beach vacation")

       assert "question_queue" in result
       assert len(result["question_queue"]) >= 3
       assert len(result["question_queue"]) <= 6
   ```

2. **Destination Parsing Tests**
   ```python
   def test_parse_destinations_handles_malformed_input(self):
       malformed_text = "Some random text without numbers"
       destinations = parse_destinations(malformed_text)

       assert len(destinations) == 3  # Always returns 3
       assert destinations[0]["name"] == "Option 1"  # Fallback
   ```

3. **API Endpoint Tests**
   ```python
   def test_chat_message_requires_authentication(self):
       response = self.client.post("/destination_search/chat/", {
           "trip_id": 1,
           "message": "test"
       })
       assert response.status_code == 401  # Unauthorized
   ```

---

### Integration Tests

File: `backend/tests/integration_tests.py`

**Full User Journey Tests:**
```python
def test_complete_destination_discovery_flow(self):
    # 1. Register user
    # 2. Create trip
    # 3. Send initial message
    # 4. Answer all questions
    # 5. Receive destinations
    # 6. Select destination
    # 7. Verify trip updated
```

---

### Test Database Setup

```python
class CustomTestRunner(DiscoverRunner):
    def teardown_databases(self, old_config, **kwargs):
        """Custom cleanup to prevent connection issues"""
        from django.db import connections
        for conn in connections.all():
            conn.close()
        super().teardown_databases(old_config, **kwargs)
```

**Why Custom Runner?**
- Django test runner sometimes leaves open connections
- Causes "database is being accessed by other users" errors
- Custom runner explicitly closes connections before cleanup

---

## Key Takeaways

**Backend Strengths:**
1. **User Isolation**: All queries filtered by `user=request.user` (security)
2. **Dynamic Serializers**: Optimize payload size for list vs detail views
3. **Atomic Transactions**: Conversation updates wrapped in `transaction.atomic()` (data integrity)
4. **Rate Limiting**: Protect expensive AI endpoints (10/min per user)
5. **Environment-Based Config**: Same code runs in dev/prod via environment variables

**Design Patterns Used:**
- **ViewSets**: DRF's ModelViewSet for automatic CRUD endpoints
- **Nested Serializers**: Reduce HTTP requests (include related objects)
- **Custom Actions**: Extend ViewSets with `@action` decorator
- **Method Overriding**: `perform_create()` to inject user, `get_queryset()` to filter
- **Middleware Pattern**: CORS, security headers, WhiteNoise (static files)

**Interview Talking Points:**
- "We use dynamic serializer selection (`get_serializer_class()`) to return lightweight data in list views and full details in retrieve views, optimizing both bandwidth and performance."
- "The chat endpoint is complex because it integrates Django's HTTP handling with LangGraph's AI workflow, persisting state in PostgreSQL between requests."
- "User isolation is enforced at the query level, not application logic. Every ViewSet's `get_queryset()` filters by `user=request.user`, making it impossible to leak data."

---

**Related Documentation:**
- [LANGGRAPH_WORKFLOW.md](./LANGGRAPH_WORKFLOW.md) - AI workflow integration
- [API_DESIGN.md](./API_DESIGN.md) - Endpoint specifications
- [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - Models and relationships
- [ADR 001: Django REST Framework](./adr/001-django-rest-framework-choices.md) - Why DRF
