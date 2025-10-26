# Database Schema Documentation

> **Database**: PostgreSQL 15 via Neon DB (Serverless) | **ORM**: Django 4.2 | **Status**: ✅ Core schema complete

## Table of Contents
- [Why PostgreSQL and Neon DB](#why-postgresql-and-neon-db)
- [Schema Overview](#schema-overview)
- [Core Models](#core-models)
- [Relationships and Foreign Keys](#relationships-and-foreign-keys)
- [Indexing Strategy](#indexing-strategy)
- [Migration Strategy](#migration-strategy)

---

## Why PostgreSQL and Neon DB

### Why PostgreSQL Over NoSQL?

**Decision Factors:**

1. **Relational Data Structure**
   - Trips have destinations, users, conversations
   - Messages belong to conversations
   - Strong relationships between entities
   - ACID transactions critical for future payment features

2. **Complex Queries**
   - Filter trips by status, destination, date ranges
   - Join conversations with messages in one query
   - Aggregate functions (COUNT messages, SUM budgets)

3. **Data Integrity**
   - Foreign key constraints prevent orphaned records
   - NOT NULL constraints ensure data quality
   - Unique constraints prevent duplicates

**What We'd Lose with MongoDB:**
- ❌ No foreign key enforcement (orphaned references possible)
- ❌ No JOIN operations (multiple queries or denormalization)
- ❌ No transactions across collections (pre-4.0)
- ❌ Django ORM benefits (would need MongoEngine)

**Trade-offs Accepted:**
- Schema changes require migrations (vs. schema-less MongoDB)
- Vertical scaling limits (but Neon auto-scales)

---

### Why Neon DB Specifically?

**Neon DB = Serverless PostgreSQL**

**Key Benefits:**

| Feature | Neon DB | AWS RDS | Heroku Postgres |
|---------|---------|---------|-----------------|
| **Auto-scaling** | ✅ Scales to zero when idle | ❌ Always on, always billed | ❌ Always on |
| **Instant Branching** | ✅ Create DB copy in seconds | ❌ Manual snapshots | ❌ Fork add-on ($50/mo) |
| **Free Tier** | ✅ 3 GB storage, 100 hours compute | ❌ No free tier | ❌ Discontinued |
| **Point-in-Time Recovery** | ✅ 7-day rollback | ✅ Via snapshots | ✅ Premium plans |
| **Connection Pooling** | ✅ Built-in | ❌ Needs RDS Proxy | ✅ Built-in |
| **Pricing** | Pay for compute hours used | Pay for instance uptime | $5/mo minimum (hobby tier gone) |

**Interview-Worthy Insight:**
> "Neon's instant database branching is a game-changer for development. We can create a full copy of production data in 5 seconds, test migrations on it, then throw it away. With AWS RDS, this would take 10+ minutes and cost money to run."

**Connection Configuration** (`settings.py:106-119`):

```python
if os.environ.get("DATABASE_URL"):
    # Production: Neon DB connection string
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

---

## Schema Overview

### Entity-Relationship Diagram (Text Format)

```
┌─────────────────┐
│   auth_user     │  (Django built-in)
│─────────────────│
│ PK id           │
│    username     │
│    email        │
│    password     │ (hashed)
│    ...          │
└────────┬────────┘
         │ 1
         │
         │ OneToOne
         ▼
┌─────────────────────────┐           ┌──────────────────┐
│  api_userpreferences    │           │ api_destination  │
│─────────────────────────│           │──────────────────│
│ PK id                   │           │ PK id            │
│ FK user_id (OneToOne)   │           │    name          │
│    preferences_text     │           │    city          │
│    budget_min           │           │    country       │
│    budget_max           │           │    description   │
│    preferred_group_size │           │    latitude      │
│    created_at           │           │    longitude     │
│    updated_at           │           │    ...           │
└─────────────────────────┘           └────────┬─────────┘
         │                                     │
         │ OneToMany                           │
         │ (via User)                          │
         ▼                                     │
┌─────────────────────────┐                   │
│      api_trip           │                   │
│─────────────────────────│                   │
│ PK id                   │                   │
│ FK user_id              │◄──────────────────┘ FK (optional)
│ FK destination_id       │
│    title                │
│    description          │
│    start_date           │
│    end_date             │
│    budget               │
│    status               │ (10 choices)
│    travelers_count      │
│    created_at           │
│    updated_at           │
└────────┬────────────────┘
         │ 1
         │
         │ OneToOne
         ▼
┌──────────────────────────────────┐
│ destination_search_tripconversation │
│──────────────────────────────────│
│ PK id                            │
│ FK trip_id (OneToOne)            │
│    created_at                    │
└────────┬─────────────────────────┘
         │ 1
         │
         ├──────────────────────┬─────────────────────────┐
         │ OneToMany            │ OneToMany               │ OneToOne
         ▼                      ▼                         ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌───────────────────────┐
│ destination_search_ │  │ destination_search_ │  │ destination_search_   │
│     message         │  │  recommendations    │  │  conversationstate    │
│─────────────────────│  │─────────────────────│  │───────────────────────│
│ PK id               │  │ PK id               │  │ PK id                 │
│ FK conversation_id  │  │ FK conversation_id  │  │ FK conversation_id    │
│    is_user (bool)   │  │    locations (JSON) │  │    current_stage      │
│    content (text)   │  │    created_at       │  │    user_info (text)   │
│    timestamp        │  └─────────────────────┘  │    question_queue     │
└─────────────────────┘                           │    destinations_text  │
                                                  │    questions_asked    │
                                                  │    total_questions    │
                                                  │    created_at         │
                                                  │    updated_at         │
                                                  └───────────────────────┘

┌─────────────────────┐
│ api_planningsession │
│─────────────────────│
│ PK id               │
│ FK trip_id          │
│    current_stage    │ (7 choices)
│    is_active        │
│    session_data     │ (JSONField)
│    stages_completed │ (JSONField)
│    started_at       │
│    last_interaction │
│    completed_at     │
└─────────────────────┘
```

---

## Core Models

### 1. User & Preferences

#### `auth_user` (Django Built-in)
```python
# Django's default User model - we don't modify it
Fields:
  - id (PK, AutoField)
  - username (CharField, unique, max_length=150)
  - email (EmailField, max_length=254)
  - password (CharField, max_length=128) - bcrypt hashed
  - first_name (CharField, max_length=150)
  - last_name (CharField, max_length=150)
  - is_staff, is_active, is_superuser (BooleanFields)
  - date_joined (DateTimeField)
```

**Why We Don't Extend User:**
- Django's User model is well-tested and secure
- Easy to use with Django admin
- Compatible with all Django auth packages
- UserPreferences handles custom fields via OneToOne

---

#### `api_userpreferences`

File: `backend/api/models.py:9-37`

```python
class UserPreferences(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="preferences")

    # AI-discovered preferences
    preferences_text = models.TextField(blank=True)

    # Optional structured data (future use)
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    preferred_group_size = models.PositiveIntegerField(default=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Design Decisions:**

1. **OneToOne vs. Extend User**
   - ✅ OneToOne: Cleaner separation, easier to query independently
   - ❌ Extend User: Modifies Django's auth tables, harder to maintain

2. **preferences_text (TextField)**
   - Stores free-form AI-discovered preferences
   - Example: "Prefers beach destinations, luxury accommodations, budget $3000-5000, travels in summer"
   - Flexible for LLM to update during conversations

3. **Structured Fields (budget_min, budget_max)**
   - Future: Filter trips by budget range
   - Future: Show personalized destination recommendations
   - Currently optional (null=True, blank=True)

**Auto-Creation** (`api/serializers.py:32-37`):
```python
def create(self, validated_data):
    """Create user and associated preferences"""
    user = User.objects.create_user(**validated_data)
    # Auto-create UserPreferences when user registers
    UserPreferences.objects.create(user=user)
    return user
```

**Why**: Ensures every user has a preferences object, avoids null checks in code.

---

### 2. Destinations

#### `api_destination`

File: `backend/api/models.py:39-69`

```python
class Destination(models.Model):
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)

    # Travel info
    best_time_to_visit = models.CharField(max_length=200, null=True, blank=True)
    average_cost_per_day = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    # Geographic coordinates
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["name", "country"]  # Prevent duplicate "Bali, Indonesia"
```

**Design Decisions:**

1. **unique_together = ["name", "country"]**
   - Prevents duplicate destinations
   - Example: Can't have two "Bali, Indonesia" entries
   - Allows "Paris, France" and "Paris, Texas"

2. **Optional Fields (null=True, blank=True)**
   - Not all destinations have complete data initially
   - AI-generated destinations might only have name + country
   - Can be enriched later via admin panel or API integrations

3. **Geographic Coordinates**
   - Future: Show destinations on map
   - Future: Calculate distances, suggest nearby destinations
   - DecimalField with 6 decimal places = ~10cm accuracy (sufficient)

**Population Strategy:**
- AI-generated destinations create stub records (name + country only)
- Admin can manually enrich with descriptions, coordinates, etc.
- Future: Integrate with Google Places API for auto-enrichment

---

### 3. Trips

#### `api_trip`

File: `backend/api/models.py:71-126`

```python
class Trip(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trips")
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)

    # Foreign keys
    destination = models.ForeignKey(Destination, on_delete=models.SET_NULL, null=True, blank=True)

    # Trip details
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Status tracking (10 choices)
    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("ai_chat_active", "AI Chat Active"),
        ("destinations_selected", "Destination Selected"),
        ("hotels_selected", "Hotels Selected"),
        ("flights_selected", "Flights Selected"),
        ("activities_planned", "Activities Planned"),
        ("itinerary_complete", "Itinerary Complete"),
        ("booked", "Booked"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    status = models.CharField(max_length=21, choices=STATUS_CHOICES, default="planning")

    travelers_count = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]  # Newest first
```

**Design Decisions:**

1. **Status Progression**
   ```
   planning → ai_chat_active → destinations_selected → hotels_selected
     → flights_selected → activities_planned → itinerary_complete → booked → completed
   ```

   **Why 10 statuses?**
   - Track user's progress through planning workflow
   - Enable filtering ("show me all trips in planning stage")
   - Frontend can show progress indicators
   - Backend can enforce state transitions

2. **destination = ForeignKey (SET_NULL)**
   - `on_delete=models.SET_NULL` - If destination deleted, trip remains (don't cascade)
   - `null=True, blank=True` - Trip can be created without destination (selected via AI chat)

3. **user = ForeignKey (CASCADE)**
   - `on_delete=models.CASCADE` - If user deleted, delete all their trips
   - Critical for GDPR compliance (user deletion)

4. **budget = DecimalField**
   - `max_digits=10, decimal_places=2` - Supports up to $99,999,999.99
   - DecimalField (not FloatField) for precise money calculations

5. **ordering = ["-created_at"]**
   - Default sort: newest trips first
   - Negative prefix = descending order
   - Applied to all queries unless overridden

**Computed Properties** (`models.py:112-122`):

```python
def duration_days(self):
    """Calculate trip duration in days"""
    if self.start_date and self.end_date:
        return (self.end_date - self.start_date).days + 1
    return None

def is_future_trip(self):
    """Check if trip is in the future"""
    if self.start_date:
        return self.start_date > timezone.now().date()
    return True  # Default to True if no date set
```

**Why Computed, Not Stored?**
- Always accurate (no stale data if dates change)
- No extra storage needed
- Easy to serialize in API responses

---

### 4. Conversation System

#### `destination_search_tripconversation`

File: `backend/destination_search/models.py:9-17`

```python
class TripConversation(models.Model):
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name="destination_conversation")
    created_at = models.DateTimeField(auto_now_add=True)
```

**Why OneToOne?**
- Each trip has ONE destination discovery conversation
- Can't have multiple concurrent conversations for same trip
- Simplifies frontend logic (no conversation selection UI needed)

**Cascade Behavior:**
- If Trip deleted → Conversation deleted (and all messages, recommendations, state)

---

#### `destination_search_message`

File: `backend/destination_search/models.py:19-33`

```python
class Message(models.Model):
    conversation = models.ForeignKey(TripConversation, on_delete=models.CASCADE, related_name="messages")
    is_user = models.BooleanField()  # True = user, False = AI
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]  # Oldest first (chronological)
```

**Design Decisions:**

1. **is_user (Boolean) vs. Separate Tables**
   - ✅ One table: Simple queries, easy to order chronologically
   - ❌ Two tables (UserMessage, AIMessage): More complex joins, harder to paginate

2. **content (TextField)**
   - No length limit (AI responses can be long)
   - Supports multi-paragraph destination descriptions

3. **ordering = ["timestamp"]**
   - Chronological order (oldest first)
   - Frontend displays as chat history

**Query Example:**
```python
# Get all messages for a trip
trip.destination_conversation.messages.all()
# Returns: [msg1, msg2, msg3, ...] in chronological order
```

---

#### `destination_search_recommendations`

File: `backend/destination_search/models.py:35-44`

```python
class Recommendations(models.Model):
    conversation = models.ForeignKey(TripConversation, on_delete=models.CASCADE, related_name="recommendations")
    locations = models.JSONField()  # List of 3 destination dicts
    created_at = models.DateTimeField(auto_now_add=True)
```

**JSONField Structure:**

```json
[
  {
    "name": "Bali",
    "country": "Indonesia",
    "description": "Perfect luxury beach resort destination with world-class spas and restaurants. Great weather year-round, affordable luxury."
  },
  {
    "name": "Maldives",
    "country": "",
    "description": "Ultimate luxury island experience with overwater bungalows. Crystal clear water, excellent diving."
  },
  {
    "name": "Santorini",
    "country": "Greece",
    "description": "Beautiful beaches with upscale amenities, stunning sunsets, romantic atmosphere."
  }
]
```

**Why JSONField?**
- Flexible structure (AI output varies)
- No need for separate DestinationRecommendation model
- Easy to query latest recommendations: `conversation.recommendations.last()`

**Why Allow Multiple Recommendations?**
- User might say "show me different options" → Generate new recommendations
- History tracking (what was recommended on day 1 vs day 2)
- Currently frontend only shows latest

---

#### `destination_search_conversationstate`

File: `backend/destination_search/models.py:46-98`

```python
class ConversationState(models.Model):
    conversation = models.OneToOneField(TripConversation, on_delete=models.CASCADE, related_name="state")

    # Workflow stage
    WORKFLOW_STAGES = [
        ("initial", "Getting Initial Preferences"),
        ("generating_questions", "Generating Clarifying Questions"),
        ("asking_clarifications", "Asking Clarification Questions"),
        ("generating_destinations", "Generating Destination Recommendations"),
        ("destinations_complete", "Destinations Generated"),
        ("commitment_detected", "User Committed to Destination"),
    ]
    current_stage = models.CharField(max_length=50, choices=WORKFLOW_STAGES, default="initial")

    # LangGraph state persistence
    user_info = models.TextField(default="")  # Accumulated answers
    question_queue = models.JSONField(default=list)  # Remaining questions
    current_question_index = models.IntegerField(default=0)
    destinations_text = models.TextField(blank=True, default="")  # Raw LLM output

    # Metadata
    questions_asked = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**This is the CRITICAL table for AI workflow persistence.**

**Key Fields:**

1. **user_info** (Accumulated Context)
   - Starts: "I want a beach vacation"
   - After Q1: "I want a beach vacation. Budget is $3000"
   - After Q2: "I want a beach vacation. Budget is $3000. July"
   - Final: "I want a beach vacation. Budget is $3000. July. 7 days. Luxury hotels."

2. **question_queue** (JSONField List)
   - Starts: `["What's your budget?", "When?", "How long?"]`
   - After Q1: `["When?", "How long?"]`
   - After Q2: `["How long?"]`
   - After Q3: `[]` (empty → generate destinations)

3. **current_stage** (Workflow Tracking)
   - Frontend shows different UI based on stage
   - Backend routes logic based on stage
   - Progress indicator: `questions_asked / total_questions`

**Computed Properties:**

```python
def is_complete(self):
    return self.current_stage in ["destinations_complete", "commitment_detected"]

def get_progress_percentage(self):
    if self.total_questions > 0:
        return int((self.questions_asked / self.total_questions) * 100)
    return 0
```

**Why OneToOne?**
- Each conversation has ONE state
- State updates are atomic (not historical)
- If we needed state history, we'd use ForeignKey with `created_at` timestamps

---

### 5. Planning Sessions

#### `api_planningsession`

File: `backend/api/models.py:131-239`

```python
class PlanningSession(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="planning_sessions")

    # Planning stages
    PLANNING_STAGES = [
        ("destination", "Destination Selection"),
        ("accommodation", "Hotel/Accommodation Planning"),
        ("flights", "Flight Planning"),
        ("activities", "Activity Planning"),
        ("itinerary", "Itinerary Building"),
        ("finalization", "Final Review"),
        ("completed", "Planning Completed"),
    ]
    current_stage = models.CharField(max_length=20, choices=PLANNING_STAGES, default="destination")

    is_active = models.BooleanField(default=True)
    session_data = models.JSONField(default=dict, blank=True)  # Stage-specific data
    stages_completed = models.JSONField(default=list, blank=True)  # ["destination", "accommodation", ...]

    started_at = models.DateTimeField(auto_now_add=True)
    last_interaction_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_interaction_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["trip"],
                condition=~models.Q(current_stage="completed"),
                name="unique_active_session_per_trip",
            )
        ]
```

**Design Decisions:**

1. **ForeignKey (not OneToOne)**
   - Trip can have multiple planning sessions over time
   - Example: User plans trip, cancels, starts new planning session later
   - Only ONE active (non-completed) session per trip (enforced by constraint)

2. **session_data (JSONField)**
   - Flexible storage for stage-specific data
   - Example: `{"selected_hotel_ids": [1, 5, 8], "budget_breakdown": {...}}`
   - Avoids creating separate tables for each planning stage

3. **stages_completed (JSONField List)**
   - Tracks which stages user has finished
   - Example: `["destination", "accommodation"]`
   - Used for progress calculation

4. **UniqueConstraint**
   ```python
   models.UniqueConstraint(
       fields=["trip"],
       condition=~models.Q(current_stage="completed"),
       name="unique_active_session_per_trip",
   )
   ```

   **What This Does:**
   - Only ONE non-completed planning session per trip
   - Completed sessions don't count (can have multiple historical sessions)
   - Database-level enforcement (safer than application logic)

**Methods:**

```python
def advance_to_next_stage(self):
    """Move to next planning stage"""
    self.mark_stage_completed(self.current_stage)
    next_stage = self.get_next_stage()
    self.current_stage = next_stage
    if next_stage == "completed":
        self.is_active = False
        self.completed_at = timezone.now()
    self.save()
```

---

## Relationships and Foreign Keys

### Cascade Behaviors

| Model | Foreign Key | on_delete Behavior | Rationale |
|-------|-------------|-------------------|-----------|
| **UserPreferences** | user | CASCADE | Delete prefs when user deleted (GDPR) |
| **Trip** | user | CASCADE | Delete trips when user deleted (GDPR) |
| **Trip** | destination | SET_NULL | Keep trip if destination deleted (admin cleanup) |
| **TripConversation** | trip | CASCADE | Delete conversation if trip deleted |
| **Message** | conversation | CASCADE | Delete messages if conversation deleted |
| **Recommendations** | conversation | CASCADE | Delete recs if conversation deleted |
| **ConversationState** | conversation | CASCADE | Delete state if conversation deleted |
| **PlanningSession** | trip | CASCADE | Delete sessions if trip deleted |

**Key Principle**: User deletion cascades everything (GDPR compliance). Destination deletion doesn't cascade (prevents accidental data loss).

---

### Query Examples

**Get all messages for a trip:**
```python
trip = Trip.objects.get(id=10)
messages = trip.destination_conversation.messages.all()
# SQL: SELECT * FROM destination_search_message WHERE conversation_id = (SELECT id FROM destination_search_tripconversation WHERE trip_id = 10) ORDER BY timestamp
```

**Get latest recommendations:**
```python
trip = Trip.objects.get(id=10)
latest_recs = trip.destination_conversation.recommendations.last()
# SQL: SELECT * FROM destination_search_recommendations WHERE conversation_id = ... ORDER BY created_at DESC LIMIT 1
```

**Get conversation state:**
```python
trip = Trip.objects.get(id=10)
state = trip.destination_conversation.state
# SQL: SELECT * FROM destination_search_conversationstate WHERE conversation_id = ...
```

---

## Indexing Strategy

### Automatic Indexes (Django Default)

Django automatically creates indexes for:
- Primary keys (`id`)
- Foreign keys (`user_id`, `trip_id`, `conversation_id`, etc.)
- Unique fields (`username`)

**SQL Example:**
```sql
CREATE INDEX api_trip_user_id ON api_trip(user_id);
```

---

### Custom Indexes (Future Optimization)

**Queries We Could Optimize:**

1. **Filter trips by status**
   ```python
   Trip.objects.filter(user=request.user, status="planning")
   ```

   **Index:**
   ```python
   class Meta:
       indexes = [
           models.Index(fields=["user", "status"]),
       ]
   ```

2. **Filter trips by date range**
   ```python
   Trip.objects.filter(start_date__gte=today, start_date__lte=end_of_year)
   ```

   **Index:**
   ```python
   models.Index(fields=["start_date", "end_date"]),
   ```

3. **Search destinations by name**
   ```python
   Destination.objects.filter(name__icontains="bali")
   ```

   **Index (PostgreSQL-specific):**
   ```python
   models.Index(fields=["name"], opclasses=["gin_trgm_ops"])  # Trigram search
   ```

**Why Not Implemented Yet?**
- Premature optimization (dataset too small to benefit)
- Wait for query performance issues to emerge
- Monitor with Django Debug Toolbar in development

---

## Migration Strategy

### How Django Migrations Work

1. **Modify Model**
   ```python
   # api/models.py
   class Trip(models.Model):
       new_field = models.CharField(max_length=100)  # Add this
   ```

2. **Generate Migration**
   ```bash
   python manage.py makemigrations
   # Creates: api/migrations/0007_trip_new_field.py
   ```

3. **Review Migration**
   ```python
   # api/migrations/0007_trip_new_field.py
   class Migration(migrations.Migration):
       dependencies = [("api", "0006_previous_migration")]
       operations = [
           migrations.AddField(
               model_name="trip",
               name="new_field",
               field=models.CharField(max_length=100),
           ),
       ]
   ```

4. **Apply Migration**
   ```bash
   python manage.py migrate
   # Runs: ALTER TABLE api_trip ADD COLUMN new_field VARCHAR(100)
   ```

---

### Important Migrations to Remember

**Initial Migrations:**
- `api/migrations/0001_initial.py` - Created User, Trip, Destination models
- `destination_search/migrations/0001_initial.py` - Created conversation models

**Schema Changes:**
- Each model change generates a new migration file
- Migrations are version-controlled in Git
- Production runs migrations during deployment (`python manage.py migrate`)

---

### Migration Best Practices

**DO:**
- ✅ Test migrations on a database copy before production
- ✅ Review generated SQL (`python manage.py sqlmigrate api 0007`)
- ✅ Add `default` values when adding non-nullable fields
- ✅ Use `null=True, blank=True` for new optional fields

**DON'T:**
- ❌ Edit old migrations (breaks teammate's databases)
- ❌ Delete migrations (breaks production deployments)
- ❌ Add fields without `default` to tables with data

**Example: Safe Non-Null Field Addition**
```python
# DON'T: Will fail if table has data
new_field = models.CharField(max_length=100)

# DO: Provide default value
new_field = models.CharField(max_length=100, default="unknown")
```

---

## Key Takeaways

**Schema Design Strengths:**
1. **Relational Integrity**: Foreign keys prevent orphaned records
2. **ACID Transactions**: Critical for future payment processing
3. **User Isolation**: Every query filtered by user_id (security)
4. **JSON Flexibility**: question_queue, session_data allow schema evolution without migrations
5. **Cascade Rules**: User deletion cascades everything (GDPR compliance)

**Scalability Considerations:**
- **Current Bottleneck**: Conversation history grows unbounded (no archiving)
- **Solution**: Add `is_archived` field, move old conversations to cold storage after 6 months
- **Indexing**: Add composite indexes when dataset grows (user + status, start_date range)
- **Partitioning**: Future: Partition messages table by created_at (monthly partitions)

**Interview Talking Points:**
- "We use PostgreSQL for ACID transactions and relational integrity. User deletion cascades to all their data, which is critical for GDPR compliance."
- "JSONField for question_queue and session_data gives us schema flexibility - we can evolve the AI workflow without database migrations."
- "Neon DB's serverless architecture means we auto-scale to zero when idle, which is perfect for a startup."
- "unique_together constraint on Destination prevents duplicate 'Bali, Indonesia' entries, enforced at the database level."

---

**Related Documentation:**
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System overview
- [BACKEND_DESIGN.md](./BACKEND_DESIGN.md) - Django models and views
- [API_DESIGN.md](./API_DESIGN.md) - How API interacts with database
- [ADR 004: PostgreSQL Schema Design](./adr/004-postgresql-schema-design.md) - Design decisions rationale
