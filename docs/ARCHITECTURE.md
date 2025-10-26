# System Architecture Documentation

> **Version**: 1.0 | **Last Updated**: October 2025 | **Status**: ✅ Core features operational, 🚧 Advanced features in progress

## Table of Contents
- [High-Level System Overview](#high-level-system-overview)
- [Technology Stack](#technology-stack)
- [Component Interaction Flow](#component-interaction-flow)
- [Data Flow](#data-flow)
- [Feature Status Matrix](#feature-status-matrix)
- [Deployment Architecture](#deployment-architecture)
- [Security Architecture](#security-architecture)

---

## High-Level System Overview

MyTravelAgent is a **full-stack AI-powered vacation planning application** that guides users from initial vacation ideas to detailed itineraries through an intelligent conversational interface.

### System Philosophy

**Three-Tier Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│  React Frontend (Vite) - User Interface & State Management  │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/REST (JWT Auth)
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│  Django REST Framework - Business Logic & API Endpoints     │
│       ┌──────────────────────────────────────┐             │
│       │  LangGraph + Gemini AI               │             │
│       │  Conversation Workflow Engine        │             │
│       └──────────────────────────────────────┘             │
└──────────────────────┬──────────────────────────────────────┘
                       │ SQL Queries
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                      DATA LAYER                              │
│  PostgreSQL (Neon DB) - Persistent Storage                  │
└─────────────────────────────────────────────────────────────┘
```

**Key Architectural Principles:**
1. **Separation of Concerns**: Frontend handles UI, backend handles logic, database handles persistence
2. **Stateless API**: Each HTTP request is independent (JWT authentication)
3. **AI-First Design**: LangGraph workflow is the core of the destination discovery process
4. **User Isolation**: Every resource is scoped to the authenticated user
5. **Progressive Enhancement**: Start with AI chat, expand to full trip planning

---

## Technology Stack

### Frontend Stack

| Technology | Version | Purpose | Why Chosen |
|------------|---------|---------|------------|
| **React** | 19.1.1 | UI Framework | Component-based architecture, large ecosystem, team familiarity |
| **Vite** | 7.1.2 | Build Tool | Fast HMR, modern ESM-based builds (10x faster than Create React App) |
| **React Router** | 7.8.0 | Client-Side Routing | Standard for SPAs, supports protected routes |
| **Axios** | 1.11.0 | HTTP Client | Interceptors for JWT injection, better error handling than fetch |
| **IBM Carbon Design** | 2.72.1 | UI Component Library | Enterprise-grade components, accessibility built-in, consistent design |
| **SASS** | 1.90.0 | CSS Preprocessor | Variables, nesting, mixins for maintainable styles |
| **jwt-decode** | 4.0.0 | Token Parsing | Extract user info from JWT without backend call |

**Frontend Design Decisions:**
- **Why React over Vue/Angular?** Team expertise, larger job market, better TypeScript support (future)
- **Why Vite over Webpack?** 10x faster dev server, native ES modules, simpler config
- **Why IBM Carbon over Material-UI?** Enterprise-focused, better accessibility, less "Googly" design
- **Why Axios over Fetch?** Interceptors for auth, automatic JSON parsing, better error handling

---

### Backend Stack

| Technology | Version | Purpose | Why Chosen |
|------------|---------|---------|------------|
| **Django** | 4.2.23 | Web Framework | Batteries-included, ORM, admin panel, security defaults |
| **Django REST Framework** | 3.16.0 | API Framework | ViewSets, serializers, authentication, OpenAPI support |
| **Python** | 3.11 | Language | Excellent AI/ML ecosystem, readable syntax, async support |
| **PostgreSQL** | 15 | Database | ACID compliance, JSON support, full-text search, mature |
| **Neon DB** | - | Managed Postgres | Serverless, auto-scaling, generous free tier, instant branching |
| **Gunicorn** | 21.2.0 | WSGI Server | Production-grade, battle-tested, used by Instagram/Pinterest |
| **WhiteNoise** | 6.6.0 | Static File Serving | Serves static files without nginx in production |
| **djangorestframework-simplejwt** | 5.5.1 | JWT Auth | Stateless auth, refresh tokens, blacklisting support |

**Backend Design Decisions:**
- **Why Django over FastAPI/Flask?**
  - **vs. FastAPI**: Mature ecosystem, better ORM (Django ORM vs SQLAlchemy), built-in admin panel
  - **vs. Flask**: Batteries-included (auth, migrations, admin), less decision fatigue
- **Why PostgreSQL over MongoDB?**
  - Relational data (trips → conversations → messages), ACID transactions critical for payments (future)
- **Why Neon DB over AWS RDS/Heroku Postgres?**
  - Serverless (auto-scales to zero), instant database branching for dev environments, better free tier

---

### AI/ML Stack

| Technology | Purpose | Why Chosen |
|------------|---------|------------|
| **LangChain Core** | 0.3.29 | AI Framework | Abstracts LLM APIs, message handling, structured output |
| **LangGraph** | 0.2.58 | Workflow Orchestration | State machines for conversation flow, pause/resume across HTTP requests |
| **Google Gemini API** | (via langchain-google-genai) | LLM Provider | Fast (gemini-2.0-flash), cost-effective ($0.15/1M tokens), good at structured output |
| **Pydantic** | 2.x | Data Validation | Type-safe state definitions, runtime validation, integrates with LangChain |

**AI Design Decisions:**
- **Why LangGraph over plain LangChain?**
  - Need to pause workflow after generating questions, resume after user answers
  - State persistence across HTTP requests (Django controls Q&A loop)
- **Why Gemini over OpenAI/Anthropic?**
  - **vs. OpenAI GPT-4**: 3x cheaper, 2x faster (gemini-2.0-flash vs gpt-4-turbo)
  - **vs. Claude**: Similar quality for structured tasks, better free tier ($300 credit)
- **Why Temperature 0?**
  - Deterministic question generation (same input = same questions)
  - Critical for testing and debugging
  - Not creative writing, we want consistency

---

### DevOps Stack

| Technology | Purpose | Why Chosen |
|------------|---------|------------|
| **Docker** | Containerization | Consistent dev/prod environments, easy onboarding |
| **Docker Compose** | Local Orchestration | Run Postgres + Django + React with one command |
| **GitHub Actions** | CI/CD | Free for public repos, great Python/Node support |
| **Render** | Deployment Platform | Easy Django deployment, auto HTTPS, PostgreSQL included |
| **Neon DB** | Production Database | Separate from Render's ephemeral storage, point-in-time recovery |

**DevOps Design Decisions:**
- **Why Render over Heroku/AWS?**
  - Heroku discontinued free tier, Render has generous free tier
  - Simpler than AWS (no EC2/ELB/RDS complexity)
  - Auto-deploys from GitHub (no manual steps)
- **Why Docker for dev, not just production?**
  - New developers can run entire stack with `docker-compose up`
  - Avoids "works on my machine" (consistent Python/Postgres versions)

---

## Component Interaction Flow

### 1. User Registration & Authentication

```
┌─────────────┐                                   ┌─────────────┐
│   Browser   │                                   │   Django    │
│  (React)    │                                   │   Backend   │
└──────┬──────┘                                   └──────┬──────┘
       │                                                 │
       │ 1. POST /api/user/register                     │
       │    { username, email, password }               │
       │────────────────────────────────────────────────>│
       │                                                 │
       │                                     2. Hash password (bcrypt)
       │                                     3. Create User record
       │                                     4. Auto-create UserPreferences
       │                                                 │
       │ 5. Response: { id, username, email, ... }      │
       │<────────────────────────────────────────────────│
       │                                                 │
       │ 6. POST /api/token (login)                     │
       │    { username, password }                      │
       │────────────────────────────────────────────────>│
       │                                                 │
       │                                     7. Validate password
       │                                     8. Generate JWT tokens
       │                                                 │
       │ 9. Response: { access, refresh }               │
       │    (access valid 30 min, refresh valid 1 day)  │
       │<────────────────────────────────────────────────│
       │                                                 │
      10. Store tokens in localStorage                  │
       │                                                 │
```

**Key Points:**
- Passwords never stored in plaintext (Django's `create_user()` hashes with bcrypt)
- JWT tokens are **stateless** (server doesn't track sessions)
- Access token short-lived (30 min) for security
- Refresh token longer-lived (1 day) for UX convenience

---

### 2. Trip Creation & Management

```
┌─────────────┐                    ┌─────────────┐                    ┌──────────────┐
│   Browser   │                    │   Django    │                    │  PostgreSQL  │
└──────┬──────┘                    └──────┬──────┘                    └──────┬───────┘
       │                                   │                                  │
       │ 1. POST /api/trips/               │                                  │
       │    Headers: Authorization: Bearer {JWT}                              │
       │    Body: { title, budget, ... }   │                                  │
       │──────────────────────────────────>│                                  │
       │                                   │                                  │
       │                       2. Validate JWT (decode, check expiry)         │
       │                       3. Extract user_id from token                  │
       │                       4. Validate request data (dates, budget)       │
       │                                   │                                  │
       │                                   │ 5. INSERT INTO api_trip          │
       │                                   │    (user_id, title, budget, ...) │
       │                                   │─────────────────────────────────>│
       │                                   │                                  │
       │                                   │ 6. Return trip_id                │
       │                                   │<─────────────────────────────────│
       │                                   │                                  │
       │ 7. Response: 201 Created          │                                  │
       │    { id, title, status: "planning" }                                 │
       │<──────────────────────────────────│                                  │
       │                                   │                                  │
```

**Key Points:**
- Every API request includes JWT in `Authorization` header
- Django validates token, extracts `user_id`, filters queries by user
- Trip status auto-set to `"planning"` (will progress to `"ai_chat_active"` → `"destinations_selected"`)

---

### 3. AI-Powered Destination Discovery (CORE FEATURE)

This is the most complex flow, involving React → Django → LangGraph → Gemini API → PostgreSQL.

```
┌─────────┐          ┌─────────┐          ┌──────────┐          ┌─────────┐          ┌─────────┐
│ Browser │          │ Django  │          │LangGraph │          │ Gemini  │          │Postgres │
└────┬────┘          └────┬────┘          └────┬─────┘          └────┬────┘          └────┬────┘
     │                    │                     │                     │                    │
     │ 1. POST /destination_search/chat/       │                     │                    │
     │    { trip_id, message: "beach vacation" }                     │                    │
     │───────────────────>│                     │                     │                    │
     │                    │                     │                     │                    │
     │            2. Get/Create TripConversation                      │                    │
     │                    │────────────────────────────────────────────────────────────────>│
     │                    │                     │                     │                    │
     │                    │ 3. workflow.invoke({ info: "beach vacation" })                 │
     │                    │────────────────────>│                     │                    │
     │                    │                     │                     │                    │
     │                    │                     │ 4. Generate questions prompt            │
     │                    │                     │────────────────────>│                    │
     │                    │                     │                     │                    │
     │                    │                     │  5. LLM Response:   │                    │
     │                    │                     │     "1. Budget?     │                    │
     │                    │                     │      2. When?       │                    │
     │                    │                     │      3. Duration?"  │                    │
     │                    │                     │<────────────────────│                    │
     │                    │                     │                     │                    │
     │                    │   6. Parse questions │                    │                    │
     │                    │      question_queue = ["Budget?", "When?", "Duration?"]       │
     │                    │<────────────────────│                     │                    │
     │                    │                     │                     │                    │
     │            7. Save state to DB                                 │                    │
     │                    │────────────────────────────────────────────────────────────────>│
     │                    │   ConversationState:                      │                    │
     │                    │     user_info = "beach vacation"          │                    │
     │                    │     question_queue = [Q1, Q2, Q3]         │                    │
     │                    │     current_stage = "asking_clarifications"                    │
     │                    │                     │                     │                    │
     │ 8. Response:       │                     │                     │                    │
     │    ai_message: "What's your budget?"    │                     │                    │
     │    metadata: { question 1/3 }           │                     │                    │
     │<───────────────────│                     │                     │                    │
     │                    │                     │                     │                    │
     │ 9. User types "$3000"                   │                     │                    │
     │───────────────────>│                     │                     │                    │
     │                    │                     │                     │                    │
     │            10. Load state from DB        │                     │                    │
     │                    │<────────────────────────────────────────────────────────────────│
     │                    │                     │                     │                    │
     │            11. Append answer to user_info                      │                    │
     │                user_info = "beach vacation. $3000"             │                    │
     │            12. Pop question from queue                         │                    │
     │                question_queue = [Q2, Q3]                       │                    │
     │                    │                     │                     │                    │
     │            13. Save updated state        │                     │                    │
     │                    │────────────────────────────────────────────────────────────────>│
     │                    │                     │                     │                    │
     │ 14. Response:      │                     │                     │                    │
     │     ai_message: "When do you want to travel?"                  │                    │
     │     metadata: { question 2/3 }          │                     │                    │
     │<───────────────────│                     │                     │                    │
     │                    │                     │                     │                    │
     │  ... (repeat for Q2, Q3) ...            │                     │                    │
     │                    │                     │                     │                    │
     │ 15. User answers last question          │                     │                    │
     │───────────────────>│                     │                     │                    │
     │                    │                     │                     │                    │
     │            16. Detect empty question_queue                     │                    │
     │            17. Call destination_generator(state)               │                    │
     │                    │────────────────────>│                     │                    │
     │                    │                     │                     │                    │
     │                    │                     │ 18. Generate 3 destinations             │
     │                    │                     │     Prompt: full user_info              │
     │                    │                     │────────────────────>│                    │
     │                    │                     │                     │                    │
     │                    │                     │ 19. Response:       │                    │
     │                    │                     │     "1. Bali, Indonesia...             │
     │                    │                     │      2. Maldives...  │                    │
     │                    │                     │      3. Santorini, Greece..."          │
     │                    │                     │<────────────────────│                    │
     │                    │                     │                     │                    │
     │            20. Parse destinations (regex)                      │                    │
     │            21. Save Recommendations model                      │                    │
     │                    │────────────────────────────────────────────────────────────────>│
     │                    │   locations = [{ name: "Bali", country: "Indonesia", ... }]   │
     │                    │                     │                     │                    │
     │ 22. Response:      │                     │                     │                    │
     │     destinations: [Bali, Maldives, Santorini]                 │                    │
     │     stage: "destinations_complete"      │                     │                    │
     │<───────────────────│                     │                     │                    │
     │                    │                     │                     │                    │
     │ 23. Render destination cards            │                     │                    │
     │     User clicks "Choose Bali"           │                     │                    │
     │───────────────────>│                     │                     │                    │
     │                    │                     │                     │                    │
     │            24. Update Trip.destination = Bali                  │                    │
     │                Trip.status = "destinations_selected"           │                    │
     │                    │────────────────────────────────────────────────────────────────>│
     │                    │                     │                     │                    │
     │ 25. Response:      │                     │                     │                    │
     │     "Excellent choice! Ready for hotels!"                      │                    │
     │<───────────────────│                     │                     │                    │
     │                    │                     │                     │                    │
```

**Key Architectural Insights:**

1. **Django Controls the Loop, Not LangGraph**
   - LangGraph runs ONCE to generate question queue
   - Django serves questions one-by-one across multiple HTTP requests
   - Why? Better UX (user sees progress), easier error handling, simpler testing

2. **State Persistence in PostgreSQL**
   - `ConversationState` table stores LangGraph state between requests
   - Enables users to close browser, come back later, resume conversation
   - No need for WebSockets or long-polling

3. **Direct Destination Call**
   - When question queue is empty, Django calls `destination_generator()` directly
   - Bypasses full graph re-execution (performance optimization)
   - Works because `destination_generator()` only needs accumulated `user_info`

4. **Hybrid Architecture Benefits**
   - LangGraph: State machine, LLM abstraction, workflow definition
   - Django: HTTP handling, database transactions, user auth, rate limiting
   - PostgreSQL: Durable state storage, ACID transactions
   - Each component does what it's best at

---

### 4. Planning Session Workflow (Future Feature)

```
Trip Lifecycle:
"planning" → "ai_chat_active" → "destinations_selected" → "hotels_selected"
  → "flights_selected" → "activities_planned" → "itinerary_complete" → "booked"

Each stage managed by PlanningSession model:
- Tracks current_stage
- Stores stage-specific data in session_data JSONField
- Calculates progress_percentage
```

**Current Implementation Status:**
- ✅ Models defined (`PlanningSession`, hotel/flight/activity stubs)
- ✅ API endpoints exist (`/api/planning-sessions/`, `/advance_stage/`)
- ❌ No AI workflows for hotel/flight/activity selection yet
- ❌ Frontend UI for these stages not built

---

## Data Flow

### Write Operations (User Creates Trip)

```
1. User Input (React)
   └─> Form validation (client-side)
       └─> Axios POST to /api/trips/

2. Django Receives Request
   └─> JWT validation (extract user_id)
       └─> Serializer validation (TripCreateUpdateSerializer)
           └─> Database INSERT (Django ORM)
               └─> Return Trip object with ID

3. React Updates State
   └─> Navigate to trip detail page
       └─> Trigger GET /api/trips/{id}/ to fetch full details
```

---

### Read Operations (User Views Trips)

```
1. User Navigates to Home (React)
   └─> useEffect triggers Axios GET /api/trips/

2. Django Receives Request
   └─> JWT validation
       └─> Filter: Trip.objects.filter(user=request.user)
           └─> Paginate (10 items/page)
               └─> Serialize (TripListSerializer - includes nested destination)
                   └─> Return JSON response

3. React Renders List
   └─> Map over trips array
       └─> Display trip cards
           └─> Click card → Navigate to /trips/{id}/chat
```

---

### Conversation Persistence Flow

```
Request N (e.g., Answering Question 3)
     │
     ├─> Load ConversationState from DB
     │   - user_info: "beach vacation. $3000. July."
     │   - question_queue: ["How long?", "Accommodation?"]
     │
     ├─> Append user answer to user_info
     │   - user_info: "beach vacation. $3000. July. 7 days."
     │
     ├─> Pop question from queue
     │   - question_queue: ["Accommodation?"]
     │
     ├─> Save updated ConversationState
     │
     └─> Return next question: "What kind of accommodation?"

Request N+1 (Answering Last Question)
     │
     ├─> Load ConversationState
     │
     ├─> Append answer, pop question
     │   - question_queue: [] (empty!)
     │
     ├─> Detect empty queue → Call destination_generator()
     │
     ├─> Parse LLM response
     │
     ├─> Save Recommendations model
     │
     └─> Return destinations JSON
```

**Why This Architecture?**
- Survives browser refresh (state in DB, not memory)
- Survives server restart (PostgreSQL is persistent)
- Enables multi-device (user can switch from phone to laptop)
- Simplifies frontend (no complex state management needed)

---

## Feature Status Matrix

| Feature Category | Feature | Status | Implementation Notes |
|-----------------|---------|--------|---------------------|
| **Authentication** | User registration | ✅ Complete | Auto-creates UserPreferences |
| | JWT login/refresh | ✅ Complete | 30-min access, 1-day refresh tokens |
| | Password reset | ❌ Not implemented | Future: Email-based reset |
| | Social auth (Google, etc.) | ❌ Not implemented | Future: OAuth integration |
| **Trip Management** | Create trip | ✅ Complete | Minimal required fields (just title) |
| | List/filter trips | ✅ Complete | Pagination, status filter, search |
| | Update trip | ✅ Complete | PATCH endpoint |
| | Delete trip | ✅ Complete | Cascades to conversations |
| | Trip status tracking | ✅ Complete | 10 statuses from planning → completed |
| **AI Destination Discovery** | Initial preference capture | ✅ Complete | Natural language input |
| | Clarifying questions | ✅ Complete | 3-6 questions via LangGraph |
| | Destination generation | ✅ Complete | Exactly 3 destinations |
| | Conversation history | ✅ Complete | Load previous messages |
| | Conversation reset | ✅ Complete | Start over functionality |
| | Destination commitment | ✅ Complete | Select destination → update trip |
| **Planning Stages** | Accommodation selection | 🚧 In Progress | Models exist, no AI workflow |
| | Flight planning | 🚧 In Progress | Models exist, no AI workflow |
| | Activity planning | 🚧 In Progress | Models exist, no AI workflow |
| | Itinerary builder | 🚧 In Progress | Stage defined, no implementation |
| | Budget tracking | 🚧 In Progress | Fields exist, no detailed tracking |
| **User Preferences** | Store AI-discovered prefs | ✅ Complete | Updated during conversations |
| | Manual preference editing | ✅ Complete | API endpoint exists |
| | Preference-based suggestions | ❌ Not implemented | Future: Use prefs for recommendations |
| **Deployment** | Docker local dev | ✅ Complete | docker-compose.yml |
| | Production deployment (Render) | ✅ Complete | Auto-deploy from GitHub |
| | Database (Neon) | ✅ Complete | Serverless Postgres |
| | CI/CD pipeline | ✅ Complete | GitHub Actions (tests, linting) |

**Legend:**
- ✅ Complete: Fully implemented and tested
- 🚧 In Progress: Models/endpoints exist, but incomplete features
- ❌ Not Implemented: Planned but no code yet
- 📋 Future: Roadmap item, not started

---

## Deployment Architecture

### Development Environment (Docker Compose)

```
┌─────────────────────────────────────────────────────────────────┐
│                       Developer Machine                          │
│                                                                  │
│  ┌─────────────┐       ┌─────────────┐      ┌──────────────┐  │
│  │   React     │       │   Django    │      │  PostgreSQL  │  │
│  │  (Vite)     │       │  (runserver)│      │  Container   │  │
│  │  Port 5173  │       │  Port 8000  │      │  Port 5432   │  │
│  └──────┬──────┘       └──────┬──────┘      └──────┬───────┘  │
│         │                     │                     │           │
│         │ HTTP localhost:8000 │                     │           │
│         └────────────────────>│                     │           │
│                               │   SQL Queries       │           │
│                               └────────────────────>│           │
│                                                                  │
│  Volume Mounts:                                                 │
│    ./frontend → /app (hot reload for React)                    │
│    ./backend → /app (hot reload for Django)                    │
│    postgres_data → /var/lib/postgresql/data (persist DB)       │
└─────────────────────────────────────────────────────────────────┘

Run Command: docker-compose up
```

**Benefits:**
- One command to start entire stack
- Consistent Python/Node/Postgres versions across team
- Hot reload works (changes reflected immediately)
- No "works on my machine" issues

---

### Production Environment (Render + Neon DB)

```
                                Internet
                                   │
                                   │ HTTPS
                                   │
                    ┌──────────────▼──────────────┐
                    │    Render Load Balancer     │
                    │   (Auto HTTPS/SSL Certs)    │
                    └──────────────┬──────────────┘
                                   │
             ┌─────────────────────┼─────────────────────┐
             │                     │                     │
     ┌───────▼────────┐   ┌────────▼───────┐   ┌───────▼────────┐
     │  Frontend      │   │   Backend      │   │   Backend      │
     │  (Nginx)       │   │   (Gunicorn)   │   │   (Gunicorn)   │
     │  Static Files  │   │   Django API   │   │   Django API   │
     └───────┬────────┘   └────────┬───────┘   └───────┬────────┘
             │                     │                     │
             │                     └──────────┬──────────┘
             │                                │
             │                                │ SQL (SSL)
             │                                │
             │                     ┌──────────▼──────────┐
             │                     │   Neon DB           │
             │                     │   (Serverless       │
             │                     │   PostgreSQL)       │
             │                     │   - Auto-scaling    │
             │                     │   - Backups         │
             │                     └─────────────────────┘
             │
             │                     External APIs
             │                          │
             └──────────────────────────┼──────────────────────┐
                                        │                      │
                              ┌─────────▼──────┐    ┌─────────▼──────┐
                              │  Gemini API    │    │  Future APIs   │
                              │  (Google)      │    │  (Maps, etc.)  │
                              └────────────────┘    └────────────────┘
```

**Key Production Characteristics:**

1. **Render Handles:**
   - Automatic HTTPS with Let's Encrypt
   - Auto-deploy from GitHub (push to main → auto-build → deploy)
   - Zero-downtime deploys (blue/green deployment)
   - Health checks (`/health` endpoint)

2. **Neon DB Advantages:**
   - Separate from Render's ephemeral storage (survives deploys)
   - Auto-scales compute based on load
   - Point-in-time recovery (7-day rollback)
   - Instant database branching (create preview env from main DB in seconds)

3. **Static Files:**
   - WhiteNoise serves static files (CSS, JS) from Django
   - No need for separate CDN (yet)
   - Future: Move to CloudFront for global users

4. **Environment Variables:**
   - Render dashboard stores:
     - `DATABASE_URL` (Neon connection string)
     - `GOOGLE_API_KEY` (Gemini API key)
     - `SECRET_KEY` (Django secret)
     - `DEBUG=False`

---

## Security Architecture

### Authentication Flow Security

```
1. Registration
   - Password hashed with bcrypt (Django default)
   - Salt automatically added
   - Cost factor: 12 rounds (2^12 iterations)

2. Login
   - Password compared against hash (constant-time comparison)
   - If valid → Generate JWT with HS256 signing
   - JWT includes: user_id, exp (expiry), iat (issued at)

3. Authenticated Requests
   - Client sends: Authorization: Bearer {JWT}
   - Django validates:
     a) Signature (ensures not tampered)
     b) Expiry (ensures not expired)
     c) User exists (ensures not deleted)
   - Extract user_id from token
   - Filter all queries by user_id

4. Token Refresh
   - Refresh token has longer expiry (1 day)
   - POST /api/token/refresh → Get new access token
   - In production, old refresh token is blacklisted (one-time use)
```

---

### Input Validation & Sanitization

**Defense Layers:**

1. **Frontend Validation** (UX, NOT security)
   - Required fields
   - Date format checks
   - Budget limits

2. **Django Serializer Validation** (First backend defense)
   ```python
   def validate(self, data):
       if data.get("start_date") >= data.get("end_date"):
           raise serializers.ValidationError("End date must be after start date")
       return data
   ```

3. **SQL Injection Protection** (Critical for chat messages)
   ```python
   # views.py:52-58
   try:
       validate_no_sql_injection(message_text)
   except ValidationError:
       return Response({"error": "Invalid input detected"}, 400)
   ```

4. **Django ORM** (Automatic protection)
   - All queries use parameterized statements
   - Example: `Trip.objects.filter(user=request.user)` → `SELECT * FROM trips WHERE user_id = %s`
   - No string concatenation of user input into SQL

---

### Rate Limiting (DoS Protection)

**Per-Endpoint Limits:**

| Endpoint | Limit | Protection Against |
|----------|-------|-------------------|
| `/api/user/register` | 5/hour per IP | Fake account spam |
| `/api/token` | 10/min per IP | Brute force password attacks |
| `/destination_search/chat/` | 10/min per user | Expensive Gemini API abuse |
| `/api/trips/` (POST) | 20/hour per user | Spam trip creation |

**Implementation:**
```python
# views.py:27
@ratelimit(key="user", rate="10/m", method="POST", block=False)
```

---

### HTTPS & Security Headers

**Production Security** (`settings.py:228-236`):

```python
if not DEBUG:
    SECURE_SSL_REDIRECT = True                   # Force HTTPS
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31536000               # HSTS for 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True           # Prevent MIME sniffing
    X_FRAME_OPTIONS = "DENY"                     # Prevent clickjacking
```

**Why Each Setting:**
- `SECURE_SSL_REDIRECT`: Redirects HTTP → HTTPS (prevents MITM)
- `HSTS`: Tells browsers to ONLY use HTTPS for 1 year
- `CONTENT_TYPE_NOSNIFF`: Prevents IE from guessing MIME types
- `X_FRAME_OPTIONS`: Prevents embedding site in iframe (clickjacking defense)

---

### CORS Policy

**Development:**
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",     # Vite dev server
    "http://127.0.0.1:5173",
]
```

**Production:**
```python
CORS_ALLOWED_ORIGINS = [
    "https://my-travel-agent.onrender.com",  # Explicit whitelist
]
```

**Why NOT `CORS_ALLOW_ALL_ORIGINS = True`?**
- Would allow ANY website to call our API
- Attacker could create phishing site that calls our backend
- Explicit whitelist ensures only our frontend can access API

---

## Key Takeaways

**Architectural Strengths:**
1. **Separation of Concerns**: React (UI), Django (business logic), LangGraph (AI workflow), PostgreSQL (data)
2. **Stateless API**: JWT enables horizontal scaling (no sticky sessions needed)
3. **Pause/Resume AI Workflows**: LangGraph + Django hybrid enables multi-turn conversations across HTTP requests
4. **User Isolation**: Every query filtered by `user=request.user` prevents data leaks
5. **Modern DevOps**: Docker for dev, Render for prod, Neon for DB (minimal ops overhead)

**Scalability Considerations:**
- **Current Bottleneck**: Gemini API calls (rate limited, not cached)
- **Horizontal Scaling**: Stateless API + serverless DB = easy to add more Render instances
- **Database Scaling**: Neon auto-scales, but conversation history could grow large (consider archiving old conversations)
- **Future**: Add Redis for caching frequently asked questions, LLM response caching

**Interview Talking Points:**
- "We use a hybrid LangGraph + Django architecture where the AI generates a question roadmap, but Django controls the HTTP request/response loop. This gives us the best of both worlds: powerful AI workflow orchestration and fine-grained control over the user experience."
- "State persistence in PostgreSQL was critical - users can close their browser mid-conversation and resume later. This wouldn't be possible with in-memory state or WebSocket connections."
- "JWT authentication is stateless, which means we can scale horizontally without worrying about session affinity or Redis-backed sessions."
- "We chose Neon DB over traditional Postgres hosting because it's serverless - we don't pay for idle time, and we get instant database branching for feature development."

---

**Related Documentation:**
- [LANGGRAPH_WORKFLOW.md](./LANGGRAPH_WORKFLOW.md) - Deep dive into AI conversation engine
- [API_DESIGN.md](./API_DESIGN.md) - REST API endpoint details
- [BACKEND_DESIGN.md](./BACKEND_DESIGN.md) - Django implementation details
- [FRONTEND_INTEGRATION.md](./FRONTEND_INTEGRATION.md) - React component architecture
- [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - PostgreSQL schema design
