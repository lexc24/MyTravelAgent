# API Design Documentation

> **Status**: ✅ **Core endpoints fully implemented** | 🚧 **Future features planned (hotels, flights, activities)**

## Table of Contents
- [API Design Philosophy](#api-design-philosophy)
- [Authentication Strategy](#authentication-strategy)
- [Endpoint Documentation](#endpoint-documentation)
- [Request/Response Patterns](#requestresponse-patterns)
- [Error Handling](#error-handling)
- [Rate Limiting Strategy](#rate-limiting-strategy)
- [CORS Configuration](#cors-configuration)
- [Serialization Strategy](#serialization-strategy)

---

## API Design Philosophy

### RESTful Conventions

**Core Principles:**
- Resources are nouns (`/trips`, `/conversations`), not verbs (`/get-trip`, `/create-conversation`)
- HTTP methods map to CRUD: `GET` (read), `POST` (create), `PUT/PATCH` (update), `DELETE` (destroy)
- Status codes convey meaning: `200` (success), `201` (created), `400` (bad request), `404` (not found), `429` (rate limited)
- Resource relationships use nested URLs: `/trips/:tripId/chat`

**Example Design Decision:**

```
✅ GET    /api/trips/123/                   # Retrieve trip 123
✅ POST   /api/trips/                       # Create new trip
✅ PATCH  /api/trips/123/                   # Update trip 123
✅ DELETE /api/trips/123/                   # Delete trip 123

❌ GET    /api/get-trip?id=123              # Not RESTful (verb in URL)
❌ POST   /api/delete-trip                  # Wrong method for delete
```

**Why REST Over GraphQL?**
- **Simplicity**: Team familiarity with REST, no GraphQL learning curve
- **Django REST Framework**: Mature ecosystem, excellent documentation
- **Caching**: Standard HTTP caching works out-of-the-box
- **Tooling**: Postman, Swagger, curl all work natively

**Trade-offs Accepted:**
- Over-fetching: `/trips/` returns all trip fields even if frontend only needs title
- Multiple requests: Getting trip + conversation requires 2 calls (GraphQL would do 1)
- No schema introspection: Frontend can't query available fields

---

## Authentication Strategy

### JWT Token-Based Authentication

**Why JWT?**
- Stateless: No server-side session storage needed (scales horizontally)
- Secure: Signed tokens prevent tampering
- Standard: Industry-standard (RFC 7519)
- Mobile-friendly: Easy to store in mobile apps

**Token Configuration** (`settings.py:161-166`):

```python
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),      # Short-lived for security
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),         # Longer for convenience
    "ROTATE_REFRESH_TOKENS": not DEBUG,                  # Rotate in production only
    "BLACKLIST_AFTER_ROTATION": not DEBUG,               # Blacklist old tokens
}
```

**Token Lifecycle:**

```
1. User Registers/Logs In
   POST /api/token
   { "username": "user", "password": "pass" }

   Response:
   {
     "access": "eyJhbGciOiJIUzI1NiIs...",    # Valid 30 minutes
     "refresh": "eyJhbGciOiJIUzI1NiIs..."    # Valid 1 day
   }

2. Authenticated Request
   GET /api/trips/
   Headers: { Authorization: "Bearer eyJhbGciOiJIUzI1NiIs..." }

3. Token Expires (after 30 min)
   GET /api/trips/
   Response: 401 Unauthorized

4. Refresh Token
   POST /api/token/refresh
   { "refresh": "eyJhbGciOiJIUzI1NiIs..." }

   Response:
   {
     "access": "eyJhbGciOiJIUzI1NiIs...",    # New access token
     "refresh": "eyJhbGciOiJIUzI1NiIs..."    # New refresh token (if ROTATE enabled)
   }
```

**Frontend Integration** (`frontend/src/api.js:10-21`):

```javascript
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(ACCESS_TOKEN);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;  // Inject token
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);
```

**Security Considerations:**
- ✅ Tokens stored in `localStorage` (simple, but vulnerable to XSS)
- ✅ Short access token lifetime (30 min) limits damage if stolen
- ✅ HTTPS required in production (prevents token interception)
- ❌ No token rotation on frontend (requires manual logout/login)
- ❌ No automatic refresh on 401 (frontend doesn't retry with refresh token)

**Future Improvements:**
- [ ] Implement automatic token refresh in Axios interceptor
- [ ] Move tokens to `httpOnly` cookies (prevents XSS)
- [ ] Add token revocation on logout
- [ ] Implement sliding sessions (extend token on activity)

### Permission Strategy

**Per-Endpoint Authorization** (`views.py:66`):

```python
permission_classes = [IsAuthenticated]

def get_queryset(self):
    """Only return trips for the authenticated user"""
    return Trip.objects.filter(user=self.request.user)
```

**User Isolation Pattern:**

Every user-owned resource query includes `user=request.user`:
- **Trips**: `Trip.objects.filter(user=request.user)`
- **Conversations**: `TripConversation.objects.filter(trip__user=request.user)`
- **Preferences**: `UserPreferences.objects.filter(user=request.user)`

**Why This Works:**
- Database-level isolation: No risk of leaking other users' data
- Automatic in ViewSets: `get_queryset()` filters everything
- Simple to audit: Search for `.filter(user=` to verify all endpoints

**Example Attack Prevention:**

```python
# views.py:67 - Without user filter, any user could access any trip
❌ trip = get_object_or_404(Trip, id=trip_id)  # User A can access User B's trip

# Correct implementation
✅ trip = get_object_or_404(Trip, id=trip_id, user=request.user)
```

---

## Endpoint Documentation

### Authentication Endpoints

#### 1. User Registration
```
POST /api/user/register
```

**Request Body:**
```json
{
  "username": "traveler123",
  "email": "traveler@example.com",
  "password": "SecureP@ss123",
  "first_name": "John",      // Optional
  "last_name": "Doe"          // Optional
}
```

**Response (201 Created):**
```json
{
  "id": 5,
  "username": "traveler123",
  "email": "traveler@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "preferences": {
    "id": 5,
    "preferences_text": "",
    "budget_min": null,
    "budget_max": null,
    "preferred_group_size": 2,
    "updated_at": "2025-10-24T10:30:00Z"
  }
}
```

**Rate Limit**: 5 requests per hour per IP (`views.py:29`)

**Implementation Notes** (`api/serializers.py:32-37`):
```python
def create(self, validated_data):
    """Create user and associated preferences"""
    user = User.objects.create_user(**validated_data)
    # Auto-create UserPreferences when user registers
    UserPreferences.objects.create(user=user)
    return user
```

**Why Auto-Create Preferences?**
- Ensures every user has a preferences object (prevents null checks)
- Simplifies frontend logic (no need to create preferences separately)
- Ready for AI to populate via conversations

---

#### 2. Obtain Token (Login)
```
POST /api/token
```

**Request Body:**
```json
{
  "username": "traveler123",
  "password": "SecureP@ss123"
}
```

**Response (200 OK):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Implementation**: Uses `rest_framework_simplejwt.views.TokenObtainPairView` (built-in)

---

#### 3. Refresh Token
```
POST /api/token/refresh
```

**Request Body:**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  // New refresh if rotation enabled
}
```

---

### Trip Management Endpoints

#### 4. List Trips
```
GET /api/trips/
```

**Query Parameters:**
- `?status=planning` - Filter by status
- `?destination=5` - Filter by destination ID
- `?ordering=-created_at` - Sort by field (prefix `-` for descending)
- `?page=2` - Pagination (10 items per page)

**Response (200 OK):**
```json
{
  "count": 25,
  "next": "http://api.example.com/api/trips/?page=3",
  "previous": "http://api.example.com/api/trips/?page=1",
  "results": [
    {
      "id": 10,
      "title": "Summer Beach Getaway",
      "destination": {
        "id": 3,
        "name": "Bali",
        "country": "Indonesia",
        "description": "Tropical paradise...",
        "best_time_to_visit": "April-October",
        "average_cost_per_day": "75.00"
      },
      "start_date": "2025-07-15",
      "end_date": "2025-07-22",
      "budget": "3000.00",
      "status": "planning",
      "travelers_count": 2,
      "duration_days": 8,
      "created_at": "2025-10-20T14:30:00Z",
      "updated_at": "2025-10-24T09:15:00Z"
    }
    // ... 9 more items
  ]
}
```

**Rate Limit**: 100 requests per hour per user (`views.py:89`)

**Implementation** (`api/views.py:63-96`):
```python
class TripViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = TripPagination              # 10 per page
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "destination"]   # Enable filtering
    ordering_fields = ["created_at", "start_date", "title"]
    ordering = ["-created_at"]                     # Default order

    def get_queryset(self):
        return Trip.objects.filter(user=self.request.user)  # User isolation

    def get_serializer_class(self):
        if self.action == "list":
            return TripListSerializer               # Simplified for list view
        elif self.action in ["create", "update", "partial_update"]:
            return TripCreateUpdateSerializer       # Validation for writes
        return TripDetailSerializer                 # Full details for retrieve
```

---

#### 5. Create Trip
```
POST /api/trips/
```

**Request Body:**
```json
{
  "title": "Family Vacation 2025",
  "description": "Annual family trip",      // Optional
  "start_date": "2025-08-01",              // Optional
  "end_date": "2025-08-10",                // Optional
  "budget": "5000.00",                     // Optional
  "travelers_count": 4                     // Optional (default: 1)
}
```

**Response (201 Created):**
```json
{
  "id": 11,
  "title": "Family Vacation 2025",
  "description": "Annual family trip",
  "destination": null,                     // Set later via AI chat
  "start_date": "2025-08-01",
  "end_date": "2025-08-10",
  "budget": "5000.00",
  "travelers_count": 4,
  "status": "planning"                     // Auto-set to "planning"
}
```

**Rate Limit**: 20 requests per hour per user (`views.py:98`)

**Validation** (`api/serializers.py:156-164`):
```python
def validate(self, data):
    """Validate trip dates"""
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if start_date and end_date and start_date >= end_date:
        raise serializers.ValidationError("End date must be after start date")

    return data
```

---

#### 6. Retrieve Trip
```
GET /api/trips/{id}/
```

**Response (200 OK):**
```json
{
  "id": 10,
  "title": "Summer Beach Getaway",
  "description": "Relaxing vacation with family",
  "destination": {
    "id": 3,
    "name": "Bali",
    "country": "Indonesia",
    "description": "Tropical paradise...",
    "latitude": "-8.3405",
    "longitude": "115.0920",
    "best_time_to_visit": "April-October",
    "average_cost_per_day": "75.00"
  },
  "start_date": "2025-07-15",
  "end_date": "2025-07-22",
  "budget": "3000.00",
  "status": "destinations_selected",
  "travelers_count": 2,
  "duration_days": 8,
  "total_estimated_cost": null,           // Future feature
  "user": {
    "id": 5,
    "username": "traveler123",
    "email": "traveler@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "created_at": "2025-10-20T14:30:00Z",
  "updated_at": "2025-10-24T09:15:00Z"
}
```

---

#### 7. Update Trip
```
PATCH /api/trips/{id}/
```

**Request Body** (all fields optional):
```json
{
  "title": "Updated Trip Name",
  "budget": "4000.00",
  "travelers_count": 3
}
```

**Response (200 OK)**: Same as Retrieve Trip

---

#### 8. Delete Trip
```
DELETE /api/trips/{id}/
```

**Response (204 No Content)**: Empty body

**Cascade Behavior**: Deletes associated conversations, messages, and recommendations (Django `on_delete=models.CASCADE`)

---

### Destination Search (AI Chat) Endpoints

#### 9. Send Chat Message ✅ **FULLY IMPLEMENTED**
```
POST /destination_search/chat/
```

**Request Body:**
```json
{
  "trip_id": 10,
  "message": "I want a relaxing beach vacation with great food"
}
```

**Response (200 OK)** - Initial Message:
```json
{
  "user_message": {
    "id": 101,
    "is_user": true,
    "content": "I want a relaxing beach vacation with great food",
    "timestamp": "2025-10-24T10:30:00Z"
  },
  "ai_message": {
    "id": 102,
    "is_user": false,
    "content": "What's your budget for this trip?",
    "timestamp": "2025-10-24T10:30:05Z"
  },
  "conversation_id": 50,
  "stage": "asking_clarifications",
  "progress": 16,                        // Percentage (1/6 questions = 16%)
  "metadata": {
    "question_number": 1,
    "total_questions": 6
  }
}
```

**Response (200 OK)** - Final Message (Destinations Generated):
```json
{
  "user_message": {
    "id": 113,
    "is_user": true,
    "content": "I prefer luxury accommodations",
    "timestamp": "2025-10-24T10:35:00Z"
  },
  "ai_message": {
    "id": 114,
    "is_user": false,
    "content": "1. Bali, Indonesia\nPerfect luxury beach resort destination with world-class spas...\n\n2. Maldives\nUltimate luxury island experience...\n\n3. Santorini, Greece\nBeautiful beaches with upscale amenities...",
    "timestamp": "2025-10-24T10:35:08Z"
  },
  "conversation_id": 50,
  "stage": "destinations_complete",
  "progress": 100,
  "destinations": [
    {
      "name": "Bali",
      "country": "Indonesia",
      "description": "Perfect luxury beach resort destination with world-class spas..."
    },
    {
      "name": "Maldives",
      "country": "",
      "description": "Ultimate luxury island experience..."
    },
    {
      "name": "Santorini",
      "country": "Greece",
      "description": "Beautiful beaches with upscale amenities..."
    }
  ]
}
```

**Rate Limit**: 10 requests per minute per user (`views.py:27`)

**Error Responses:**

```json
// 400 Bad Request - Missing Fields
{
  "error": "trip_id and message are required"
}

// 400 Bad Request - SQL Injection Detected
{
  "error": "Invalid input detected"
}

// 404 Not Found - Trip Doesn't Exist or Doesn't Belong to User
{
  "detail": "Not found."
}

// 429 Too Many Requests - Rate Limit Exceeded
{
  "error": "Too many requests. Please wait a moment and try again."
}

// 500 Internal Server Error - LLM Failure
{
  "error": "An error occurred processing your message"
}
```

**Implementation Flow** (`destination_search/views.py:28-225`):

1. **Validate Input** (lines 47-64)
   - Check for `trip_id` and `message`
   - Run SQL injection validator
   - Verify trip ownership

2. **Create/Load Conversation** (lines 76-81)
   - Get or create `TripConversation` for this trip
   - Get or create `ConversationState`

3. **Route Based on Stage** (lines 88-169)
   - `initial` → Run LangGraph workflow, get question queue
   - `asking_clarifications` → Process answer, pop question, check if done
   - `destinations_complete` → Handle post-destination messages (commitment detection)

4. **Save AI Response** (lines 171-173)
   - Create `Message` record with `is_user=False`

5. **Return Structured Response** (lines 176-213)
   - User message, AI message, stage, progress
   - Include destinations if just generated

---

#### 10. Get Conversation History
```
GET /destination_search/conversations/{trip_id}/
```

**Response (200 OK):**
```json
{
  "conversation_id": 50,
  "trip_id": 10,
  "trip_title": "Summer Beach Getaway",
  "messages": [
    {
      "id": 101,
      "is_user": true,
      "content": "I want a relaxing beach vacation",
      "timestamp": "2025-10-24T10:30:00Z"
    },
    {
      "id": 102,
      "is_user": false,
      "content": "What's your budget for this trip?",
      "timestamp": "2025-10-24T10:30:05Z"
    }
    // ... all messages
  ],
  "state": {
    "current_stage": "asking_clarifications",
    "progress": 33,
    "questions_asked": 2,
    "total_questions": 6
  },
  "destinations": [
    // ... destinations if generated
  ]
}
```

**Response (404 Not Found):**
```json
{
  "message": "No conversation started yet for this trip"
}
```

**Use Case**: Reload conversation when user navigates back to chat page

---

#### 11. Reset Conversation
```
POST /destination_search/conversations/{trip_id}/reset/
```

**Response (200 OK):**
```json
{
  "message": "Conversation reset successfully"
}
```

**Side Effects** (`views.py:437-442`):
- Deletes `TripConversation` (cascades to messages, recommendations, state)
- Resets trip status to `"planning"`
- Clears destination assignment

---

### User Preferences Endpoints

#### 12. Get User Preferences
```
GET /api/user-preferences/
```

**Response (200 OK):**
```json
[
  {
    "id": 5,
    "preferences_text": "Beach vacations, luxury accommodations, budget $3000-5000",
    "budget_min": "3000.00",
    "budget_max": "5000.00",
    "preferred_group_size": 2,
    "updated_at": "2025-10-24T10:30:00Z"
  }
]
```

**Note**: Returns a list (DRF ViewSet convention), but will always have 1 item (OneToOne with User)

---

#### 13. Update Preferences
```
PATCH /api/user-preferences/{id}/
```

**Request Body:**
```json
{
  "preferences_text": "Updated preferences text",
  "budget_min": "2000.00",
  "budget_max": "4000.00"
}
```

---

### Planning Session Endpoints

#### 14. Create Planning Session
```
POST /api/planning-sessions/
```

**Request Body:**
```json
{
  "trip": 10
}
```

**Response (201 Created):**
```json
{
  "id": 20,
  "trip": {
    "id": 10,
    "title": "Summer Beach Getaway",
    "destination": { /* ... */ },
    "start_date": "2025-07-15",
    "end_date": "2025-07-22",
    "status": "destinations_selected"
  },
  "current_stage": "destination",
  "is_active": true,
  "session_data": {},
  "stages_completed": [],
  "started_at": "2025-10-24T10:30:00Z",
  "last_interaction_at": "2025-10-24T10:30:00Z",
  "completed_at": null,
  "progress_percentage": 0.0,
  "is_completed": false,
  "next_stage": "accommodation"
}
```

---

#### 15. Advance Planning Stage
```
POST /api/planning-sessions/{id}/advance_stage/
```

**Response (200 OK):**
```json
{
  "previous_stage": "destination",
  "current_stage": "accommodation",
  "is_complete": false
}
```

---

### Destination Browsing Endpoints

#### 16. List Destinations (Read-Only)
```
GET /api/destinations/
```

**Query Parameters:**
- `?search=bali` - Search by name, city, or country

**Response (200 OK):**
```json
[
  {
    "id": 3,
    "name": "Bali",
    "city": "Denpasar",
    "country": "Indonesia",
    "description": "Tropical paradise...",
    "best_time_to_visit": "April-October",
    "average_cost_per_day": "75.00",
    "latitude": "-8.3405",
    "longitude": "115.0920",
    "created_at": "2025-01-15T10:00:00Z",
    "updated_at": "2025-10-20T14:00:00Z"
  }
]
```

---

## Request/Response Patterns

### Consistent Error Format

All error responses follow this structure:

```json
{
  "error": "Human-readable error message"
}
```

**OR** (for validation errors):

```json
{
  "field_name": ["Error message for this field"],
  "another_field": ["Another error"]
}
```

**Example**:

```json
// 400 Bad Request
{
  "title": ["This field is required."],
  "start_date": ["Date has wrong format. Use YYYY-MM-DD."]
}
```

---

### Pagination Pattern

All list endpoints use Django REST Framework's `PageNumberPagination`:

```json
{
  "count": 42,                                    // Total items across all pages
  "next": "http://api.example.com/api/trips/?page=3",   // Next page URL (null if last)
  "previous": "http://api.example.com/api/trips/?page=1", // Previous page URL (null if first)
  "results": [ /* ... items for current page ... */ ]
}
```

**Configuration** (`api/views.py:57-60`):
```python
class TripPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"     # Allow client to override: ?page_size=25
    max_page_size = 100                     # Prevent abuse: ?page_size=10000
```

---

### Timestamp Format

All timestamps use ISO 8601 format with UTC timezone:

```
2025-10-24T10:30:00Z
```

Django automatically serializes `DateTimeField` to this format via DRF.

---

## Error Handling

### HTTP Status Code Usage

| Code | Meaning | When to Use |
|------|---------|-------------|
| 200 | OK | Successful GET, PATCH, POST (non-creation) |
| 201 | Created | Successful POST (resource created) |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Validation errors, missing required fields |
| 401 | Unauthorized | Missing/invalid JWT token |
| 403 | Forbidden | Valid token but insufficient permissions |
| 404 | Not Found | Resource doesn't exist or user doesn't own it |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Unhandled exception (LLM failure, DB error) |

---

### Error Logging

**Configuration** (`settings.py:238-262`):

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "destination_search": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",    # Verbose in dev
            "propagate": False,
        },
    },
}
```

**Usage in Views** (`views.py:221`):

```python
except Exception as e:
    logger.error(f"Error in chat_message: {str(e)}", exc_info=True)  # Log full traceback
    return Response(
        {"error": "An error occurred processing your message"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
```

---

## Rate Limiting Strategy

### Why Rate Limit?

**Protect Against:**
- Brute force attacks on login endpoint
- Abuse of expensive AI chat endpoint (Gemini API costs money)
- Accidental infinite loops in frontend code
- Malicious users creating spam data

### Rate Limit Configuration

**Library**: `django-ratelimit` (installed via `requirements.txt`)

**Per-Endpoint Limits:**

| Endpoint | Limit | Key | Rationale |
|----------|-------|-----|-----------|
| `/api/user/register` | 5/hour | IP | Prevent fake account creation |
| `/api/trips/` (GET) | 100/hour | User | Allow normal usage, block scrapers |
| `/api/trips/` (POST) | 20/hour | User | Prevent spam trip creation |
| `/destination_search/chat/` | 10/minute | User | Expensive LLM calls, typical conversation has 6-10 messages |

**Implementation Example** (`api/views.py:28-30`):

```python
@method_decorator(
    ratelimit(key="ip", rate="5/h", method="POST", block=True),
    name="create"
)
class CreateUserView(generics.CreateAPIView):
    # ...
```

**Response When Limited** (`views.py:39-43`):

```python
def create(self, request, *args, **kwargs):
    if getattr(request, "limited", False):
        return Response(
            {"error": "Too many registration attempts. Please try again later."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return super().create(request, *args, **kwargs)
```

**Rate Limit Keys:**
- `"ip"` - Per IP address (good for public endpoints like registration)
- `"user"` - Per authenticated user (good for user-specific actions)
- `"user_or_ip"` - Use user if authenticated, else IP

---

## CORS Configuration

### What is CORS?

Cross-Origin Resource Sharing allows frontend (React on port 5173) to call backend API (Django on port 8000) from different origins.

### Configuration

**Settings** (`settings.py:168-187`):

```python
CORS_ALLOW_ALL_ORIGINS = False              # Explicit whitelist (secure)
CORS_ALLOW_CREDENTIALS = True               # Allow cookies/auth headers

if DEBUG:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:5173",            # Vite dev server
        "http://127.0.0.1:5173",            # Alternate localhost
    ]
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
else:
    CORS_ALLOWED_ORIGINS = [
        "https://my-travel-agent.onrender.com",  # Production frontend
    ]
    CSRF_TRUSTED_ORIGINS = [
        "https://my-travel-agent.onrender.com",
    ]
```

**Explicit CORS Headers** (`settings.py:189-207`):

```python
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",                 # Required for JWT Bearer tokens
    "content-type",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]
```

**Middleware Order** (`settings.py:68-78`):

```python
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",    # MUST be first
    "django.middleware.security.SecurityMiddleware",
    # ... other middleware
]
```

**Why Order Matters:**
- CORS middleware must process requests BEFORE security middleware
- If CORS is too late, browsers will reject preflight requests

---

## Serialization Strategy

### Serializer Types

**1. List Serializers** (Lightweight for Browsing)

```python
# api/serializers.py:91-112
class TripListSerializer(serializers.ModelSerializer):
    destination = DestinationSerializer(read_only=True)  # Include nested
    duration_days = serializers.ReadOnlyField()           # Computed field

    class Meta:
        model = Trip
        fields = [
            "id", "title", "destination", "start_date", "end_date",
            "budget", "status", "travelers_count", "duration_days",
            "created_at", "updated_at",
        ]  # Omit description, user details
```

**Why**: Reduces payload size for list views (might have 100 trips)

---

**2. Detail Serializers** (Complete Info for Single Resource)

```python
# api/serializers.py:114-128
class TripDetailSerializer(serializers.ModelSerializer):
    destination = DestinationSerializer(read_only=True)
    duration_days = serializers.ReadOnlyField()
    total_estimated_cost = serializers.ReadOnlyField()   # Future feature
    user = UserSerializer(read_only=True)                # Include user details

    class Meta:
        model = Trip
        fields = "__all__"  # All fields
```

**Why**: Frontend needs full context when viewing single trip

---

**3. Create/Update Serializers** (Write Operations)

```python
# api/serializers.py:130-165
class TripCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = [
            "id", "title", "description", "destination",
            "start_date", "end_date", "budget", "travelers_count", "status",
        ]
        read_only_fields = ["id", "status"]  # Can't manually set status
        extra_kwargs = {
            "description": {"required": False},
            "destination": {"required": False},
            # ... all fields optional except title
        }

    def validate(self, data):
        """Custom validation logic"""
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        if start_date and end_date and start_date >= end_date:
            raise serializers.ValidationError("End date must be after start date")
        return data
```

**Why**: Prevent invalid data, enforce business rules

---

### Dynamic Serializer Selection

**Implementation** (`api/views.py:78-84`):

```python
def get_serializer_class(self):
    """Use different serializers for different actions"""
    if self.action == "list":
        return TripListSerializer
    elif self.action in ["create", "update", "partial_update"]:
        return TripCreateUpdateSerializer
    return TripDetailSerializer
```

**DRF ViewSet Actions:**
- `list` - GET /api/trips/
- `retrieve` - GET /api/trips/123/
- `create` - POST /api/trips/
- `update` - PUT /api/trips/123/
- `partial_update` - PATCH /api/trips/123/
- `destroy` - DELETE /api/trips/123/

---

### Read-Only Fields vs. Write-Only Fields

**Read-Only** (`serializers.ReadOnlyField()` or `read_only=True`):
- Included in responses (GET)
- Ignored in requests (POST/PATCH)
- Example: `duration_days` (computed from start/end dates)

**Write-Only** (`extra_kwargs = {"password": {"write_only": True}}`):
- Required in requests (POST)
- Never included in responses (GET)
- Example: `password` (we hash it, never return plaintext)

**Example** (`api/serializers.py:23`):

```python
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "preferences"]
        extra_kwargs = {"password": {"write_only": True}}  # Never return password

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)  # Hashes password
        UserPreferences.objects.create(user=user)
        return user
```

---

### Nested Serializers

**Problem**: Trip has a foreign key to Destination. How to return destination details?

**Solution 1: Include Nested Object** (Current Approach)

```python
class TripListSerializer(serializers.ModelSerializer):
    destination = DestinationSerializer(read_only=True)  # Nested serializer
```

**Response**:
```json
{
  "id": 10,
  "destination": {
    "id": 3,
    "name": "Bali",
    "country": "Indonesia",
    "description": "...",
    "latitude": "-8.3405",
    "longitude": "115.0920"
  }
}
```

**Solution 2: Return Only ID** (Alternative)

```python
class TripListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ["id", "destination", ...]  # destination will be just an ID
```

**Response**:
```json
{
  "id": 10,
  "destination": 3  // Frontend must fetch /api/destinations/3/ separately
}
```

**Why We Chose Nested:**
- Fewer HTTP requests (better performance)
- Simpler frontend code (no cascading fetches)
- Trade-off: Larger payload (acceptable for 10-item pages)

---

## API Versioning Strategy

**Current**: No versioning (all endpoints are v1 implicitly)

**Future**: If breaking changes are needed:

```
/api/v1/trips/      # Current
/api/v2/trips/      # Future breaking changes
```

**Django URL Configuration**:
```python
urlpatterns = [
    path("api/v1/", include("api.urls")),
    path("api/v2/", include("api.urls_v2")),  # Future
]
```

---

## Key Takeaways

**What Works Well:**
- JWT authentication is simple and stateless
- User isolation via `filter(user=request.user)` prevents data leaks
- Rate limiting protects expensive AI endpoints
- Different serializers for list/detail/create optimize payload size
- Nested serializers reduce HTTP request count

**What Could Be Improved:**
- [ ] Implement automatic token refresh on frontend
- [ ] Add API documentation (Swagger/OpenAPI)
- [ ] Implement cursor-based pagination for better performance at scale
- [ ] Add request throttling for Gemini API specifically
- [ ] Move tokens to httpOnly cookies for XSS protection

**Interview Talking Points:**
- "We use JWT tokens because they're stateless, which lets us scale horizontally without session affinity"
- "Rate limiting is per-endpoint based on abuse risk: 5/hour for registration, 10/min for AI chat"
- "User isolation is enforced at the database query level, not in application logic"
- "We use different serializers for list/detail views to optimize payload size"

---

**Related Documentation:**
- [LANGGRAPH_WORKFLOW.md](./LANGGRAPH_WORKFLOW.md) - AI chat endpoint implementation
- [BACKEND_DESIGN.md](./BACKEND_DESIGN.md) - Views and serializers deep dive
- [FRONTEND_INTEGRATION.md](./FRONTEND_INTEGRATION.md) - How frontend calls these APIs
- [ADR 001: Django REST Framework](./adr/001-django-rest-framework-choices.md) - Why DRF over alternatives
