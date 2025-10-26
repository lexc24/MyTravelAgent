# ADR-004: PostgreSQL Schema Design

## Context

We needed a database that could:
- Store user accounts, trips, conversations, and messages
- Handle relationships (trips belong to users, messages belong to conversations)
- Persist LangGraph state across HTTP requests
- Support JSON data (question queues, recommendation lists)
- Enable complex queries (filter trips by status, date ranges)
- Scale for production use (thousands of users, millions of messages)
- Provide data integrity (ACID transactions for conversation updates)

## Decision

We chose **PostgreSQL 15** via **Neon DB** (serverless Postgres) with:
- Relational schema (normalized to 3NF)
- Django ORM for migrations and queries
- JSONField for flexible data (question_queue, session_data, recommendation locations)
- Foreign keys with CASCADE/SET_NULL for data integrity
- User isolation enforced via Django queries (`filter(user=request.user)`)

## Why This Approach

### PostgreSQL vs. NoSQL (MongoDB)

**Why PostgreSQL:**

| Requirement | PostgreSQL | MongoDB |
|-------------|-----------|---------|
| **Relationships** | ✅ Foreign keys, JOIN queries | ❌ Manual references, no JOIN |
| **ACID Transactions** | ✅ Full ACID compliance | ⚠️ Multi-document transactions (added in 4.0) |
| **Data Integrity** | ✅ Foreign keys, NOT NULL, UNIQUE | ❌ No schema enforcement (unless you add validation) |
| **Complex Queries** | ✅ SQL (filter by status, date range, etc.) | ⚠️ Aggregation pipeline (less intuitive) |
| **Django Integration** | ✅ Django ORM (mature, 15+ years) | ⚠️ Third-party (Djongo, MongoEngine) |
| **JSON Support** | ✅ JSONField (native in Postgres 9.2+) | ✅ Native document storage |

**Our Use Case Favors Relational:**
- **Trips → Conversations → Messages**: Clear parent-child relationships
- **User → Trips**: One-to-many (user owns multiple trips)
- **Conversation → State**: One-to-one (each conversation has one state)
- **Future payments**: Need ACID transactions (charge user, create booking, update trip status atomically)

**Where MongoDB Would Win:**
- Schema-less flexibility (but we have stable schema)
- Horizontal scaling (but Neon auto-scales)
- Nested documents (but Django's JSONField gives us this)

**Trade-offs We Accept:**
- Schema changes require migrations (vs schema-less MongoDB)
- Vertical scaling limits (but Neon auto-scales)

---

### Neon DB vs. Traditional Postgres Hosting

**Why Neon DB (Serverless Postgres):**

| Feature | Neon DB | AWS RDS | Heroku Postgres | Self-Hosted |
|---------|---------|---------|-----------------|-------------|
| **Auto-scaling** | ✅ Scales to zero | ❌ Always on | ❌ Always on | ❌ Manual |
| **Instant Branching** | ✅ Seconds | ❌ Manual snapshots | ❌ Fork add-on ($50/mo) | ❌ Manual |
| **Free Tier** | ✅ 3 GB, 100 hours | ❌ None | ❌ Discontinued | ❌ Server costs |
| **Pricing** | Pay per compute hour | Pay per instance hour | $5/mo min | $10-50/mo VPS |
| **Connection Pooling** | ✅ Built-in | ❌ Needs RDS Proxy | ✅ Built-in | ❌ Manual (PgBouncer) |
| **Backups** | ✅ Point-in-time (7 days) | ✅ Via snapshots | ✅ Premium plans | ❌ Manual |

**Key Benefit: Instant Branching**
```bash
# Create dev database from production in 5 seconds
neon branches create --name dev-branch --parent main

# Test migrations on dev-branch
python manage.py migrate --database dev-branch

# If successful, apply to main
# If failed, delete dev-branch (no cost)
```

**Why This Matters:**
- Test migrations safely (rollback if needed)
- Create preview environments (one branch per feature)
- No risk to production data

**Alternatives Considered:**

1. **AWS RDS**
   - ❌ More expensive ($15-30/mo minimum)
   - ❌ Always running (billed even when idle)
   - ❌ No instant branching (manual snapshots)

2. **Heroku Postgres**
   - ❌ Free tier discontinued (minimum $5/mo)
   - ❌ Fork add-on is $50/mo
   - ✅ Good documentation, simple setup

3. **Self-hosted (DigitalOcean/Linode)**
   - ❌ Manual backups, scaling, security patches
   - ❌ No auto-scaling
   - ✅ Full control, no vendor lock-in

**Decision**: Neon DB wins on cost (free tier), auto-scaling, and instant branching.

---

## Integration Impact

### Schema Design Principles

**1. Normalized to 3NF (Third Normal Form)**

- No duplicate data (destination details stored once in `Destination` table)
- Foreign keys prevent orphaned records
- Updates happen in one place (change destination name → all trips reflect it)

**Example:**
```
❌ Denormalized (bad):
Trip: { id: 1, destination_name: "Bali", destination_country: "Indonesia" }
Trip: { id: 2, destination_name: "Bali", destination_country: "Indonesia" }
Problem: If "Bali" changes to "Denpasar, Bali", must update all trips.

✅ Normalized (good):
Destination: { id: 3, name: "Bali", country: "Indonesia" }
Trip: { id: 1, destination_id: 3 }
Trip: { id: 2, destination_id: 3 }
Solution: Update Destination once, all trips reflect it.
```

---

**2. Foreign Key Cascade Rules**

| Model | Foreign Key | on_delete | Reason |
|-------|-------------|-----------|--------|
| Trip | user | CASCADE | Delete user → delete their trips (GDPR) |
| Trip | destination | SET_NULL | Delete destination → keep trip (prevent data loss) |
| TripConversation | trip | CASCADE | Delete trip → delete conversation |
| Message | conversation | CASCADE | Delete conversation → delete messages |
| ConversationState | conversation | CASCADE | Delete conversation → delete state |

**Why SET_NULL for destination?**
- Admin might delete "Bali" destination (cleanup)
- Don't want to cascade-delete all trips to Bali
- Trip still exists, just without destination link

**Why CASCADE for user?**
- GDPR compliance: "Right to be forgotten"
- User deletion must remove all personal data
- Easier than manually finding all related records

---

**3. JSONField for Flexible Data**

**Where We Use JSONField:**

1. **ConversationState.question_queue** (`models.py:70`)
   ```python
   question_queue = models.JSONField(default=list)
   # Stores: ["What's your budget?", "When?", "How long?"]
   ```

   **Why JSON, not separate table?**
   - Questions are temporary (not normalized data)
   - Order matters (list, not set)
   - No need to query questions individually

2. **Recommendations.locations** (`models.py:39`)
   ```python
   locations = models.JSONField()
   # Stores: [
   #   {"name": "Bali", "country": "Indonesia", "description": "..."},
   #   {"name": "Maldives", "country": "", "description": "..."},
   #   {"name": "Santorini", "country": "Greece", "description": "..."}
   # ]
   ```

   **Why JSON, not separate DestinationRecommendation table?**
   - AI output varies (might include extra fields)
   - Only displayed, never queried individually
   - Simpler schema (no extra table, no migrations for field changes)

3. **PlanningSession.session_data** (`models.py:156`)
   ```python
   session_data = models.JSONField(default=dict)
   # Stores: {"selected_hotel_ids": [1, 5], "budget_breakdown": {...}}
   ```

   **Why JSON?**
   - Each planning stage has different data needs
   - Avoid creating separate tables for each stage

---

**4. Unique Constraints**

**Destination.unique_together** (`models.py:68`):
```python
class Meta:
    unique_together = ["name", "country"]
```

**Prevents:**
```python
# Can't create two "Bali, Indonesia" entries
Destination.objects.create(name="Bali", country="Indonesia")
Destination.objects.create(name="Bali", country="Indonesia")  # Error: Duplicate
```

**Allows:**
```python
# Can create "Paris, France" and "Paris, Texas"
Destination.objects.create(name="Paris", country="France")
Destination.objects.create(name="Paris", country="USA")  # OK: Different country
```

---

**5. Ordering**

**Default Order** (`models.py:125`):
```python
class Trip(models.Model):
    class Meta:
        ordering = ["-created_at"]  # Newest first
```

**Impact:**
```python
# All queries automatically ordered
Trip.objects.all()  # Returns trips ordered by created_at DESC

# Equivalent to:
Trip.objects.all().order_by("-created_at")
```

**Why Default Ordering:**
- Users expect to see newest trips first
- Consistent across all views (list, detail, admin)
- Less code (don't repeat `order_by()` everywhere)

---

### Django ORM Patterns

**1. User Isolation (Security)**

```python
# All queries filtered by user
Trip.objects.filter(user=request.user)

# Never do this (security risk):
Trip.objects.filter(id=trip_id)  # Any user can access any trip

# Always do this:
Trip.objects.filter(id=trip_id, user=request.user)  # User can only access their trips
```

**Enforced in ViewSets** (`api/views.py:73-75`):
```python
def get_queryset(self):
    """Only return trips for the authenticated user"""
    return Trip.objects.filter(user=request.user)
```

---

**2. Select Related (Performance)**

```python
# Bad: N+1 queries
trips = Trip.objects.all()
for trip in trips:
    print(trip.destination.name)  # Each iteration queries DB

# Good: 1 query with JOIN
trips = Trip.objects.select_related("destination").all()
for trip in trips:
    print(trip.destination.name)  # No extra queries
```

**When to Use:**
- `select_related()` for ForeignKey/OneToOne (SQL JOIN)
- `prefetch_related()` for ManyToMany/Reverse ForeignKey (separate query)

---

**3. Atomic Transactions**

```python
# Ensure conversation updates are all-or-nothing
with transaction.atomic():
    conversation, _ = TripConversation.objects.get_or_create(trip=trip)
    conv_state, _ = ConversationState.objects.get_or_create(conversation=conversation)

    # Save user message
    Message.objects.create(conversation=conversation, is_user=True, content=message)

    # Save AI response
    Message.objects.create(conversation=conversation, is_user=False, content=response)

    # Update state
    conv_state.user_info += " " + message
    conv_state.save()
```

**Why Atomic:**
- If AI response fails, don't save user message (incomplete conversation)
- All updates succeed or all roll back
- Database remains consistent

---

## Code References

**Schema Definition:**
- `backend/api/models.py` - User, Trip, Destination, UserPreferences, PlanningSession
- `backend/destination_search/models.py` - TripConversation, Message, Recommendations, ConversationState

**Migrations:**
- `backend/api/migrations/0001_initial.py` - Initial schema
- `backend/destination_search/migrations/0001_initial.py` - Conversation models

**ORM Usage:**
- `backend/api/views.py:73-75` - User isolation in get_queryset()
- `backend/destination_search/views.py:74-86` - Atomic transaction for conversation updates

---

## Future Considerations

### 1. Archiving Old Conversations

**Current**: All conversations stored indefinitely.

**Problem**: Database grows unbounded (millions of messages).

**Solution**:
```python
# Add is_archived field
class Message(models.Model):
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)

# Archive conversations older than 6 months
old_conversations = TripConversation.objects.filter(
    created_at__lt=timezone.now() - timedelta(days=180)
)
Message.objects.filter(conversation__in=old_conversations).update(is_archived=True)

# Query: Only fetch non-archived messages
messages = Message.objects.filter(conversation=conversation, is_archived=False)
```

---

### 2. Composite Indexes

**Current**: Only default indexes (primary keys, foreign keys).

**Future**: Add composite indexes for common queries.

```python
class Trip(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["user", "status"]),      # Filter by user + status
            models.Index(fields=["start_date", "end_date"]),  # Date range queries
        ]
```

**When to Add:**
- Query performance issues emerge (use Django Debug Toolbar to identify slow queries)
- Database grows large (10,000+ trips per user)

---

### 3. Partitioning (for Scale)

**Current**: Single messages table.

**Future (if millions of messages)**: Partition by created_at.

```sql
-- PostgreSQL 11+ table partitioning
CREATE TABLE messages (
    id SERIAL,
    conversation_id INT,
    content TEXT,
    created_at TIMESTAMP
) PARTITION BY RANGE (created_at);

CREATE TABLE messages_2025_01 PARTITION OF messages
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE messages_2025_02 PARTITION OF messages
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
```

**Benefits:**
- Query recent messages (last month) without scanning all history
- Archive old partitions to cold storage
- Drop old partitions without VACUUM overhead

---

### 4. Full-Text Search

**Current**: Simple filter (`Destination.objects.filter(name__icontains="bali")`).

**Future**: PostgreSQL full-text search.

```python
from django.contrib.postgres.search import SearchVector

# Enable full-text search on destination name + description
Destination.objects.annotate(
    search=SearchVector("name", "description")
).filter(search="beach paradise")
```

**When to Add:**
- User wants to search destinations by keywords ("beach", "adventure", "luxury")
- Simple `icontains` is too slow (no index support)

---

## Lessons Learned

**What Worked Well:**
- JSONField for flexible data (question_queue, locations) avoided complex schemas
- Foreign key CASCADE rules enforce GDPR compliance automatically
- Neon DB's instant branching saved hours of migration testing
- Django ORM migrations are smooth (no manual SQL needed)

**What We'd Do Differently:**
- Add indexes earlier (composite index on user + status)
- Use `select_related()` from the start (avoid N+1 queries)
- Plan for archiving (add `is_archived` field to all message-like models)

**Biggest Surprise:**
- Neon DB's serverless model actually works (scales to zero, no cold start issues)
- JSONField is more flexible than expected (schema evolution without migrations)
- PostgreSQL's JSON support is excellent (can query inside JSON with `.filter(data__key="value")`)

---

## Interview Talking Point

> "We chose PostgreSQL over MongoDB because our data is relational—trips have destinations, conversations have messages, and we need ACID transactions for future payment processing. We use Neon DB (serverless Postgres) for instant database branching, which lets us test migrations on a production-like database in 5 seconds.
>
> JSONField gives us schema flexibility where we need it (question queues, session data) without sacrificing relational integrity. Foreign key CASCADE rules enforce GDPR compliance automatically—deleting a user cascades to all their data.
>
> We enforce user isolation at the database query level with `.filter(user=request.user)`, not in application logic, which makes it impossible to leak data."

---

**Related ADRs:**
- [ADR-001: Django REST Framework](./001-django-rest-framework-choices.md)
- [ADR-002: LangGraph for Conversation Flow](./002-langgraph-for-conversation-flow.md)
- [ADR-003: Gemini API Integration](./003-gemini-api-integration.md)
- [ADR-005: Docker Development Environment](./005-docker-development-environment.md)
