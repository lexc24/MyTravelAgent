# MyTravelAgent

> An AI-powered travel planning assistant that transforms your vacation ideas into personalized destination recommendations through intelligent conversations

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2.23-green.svg)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-19.1.1-blue.svg)](https://reactjs.org/)
[![License](https://img.shields.io/badge/License-Not%20Specified-lightgrey.svg)](#license)

---

## Overview

**MyTravelAgent** is a full-stack web application that revolutionizes travel planning by combining conversational AI with structured trip management. Instead of overwhelming users with endless destination options, the application engages travelers in a natural conversation to understand their preferences, budget, and travel style, then generates exactly three carefully curated destination recommendations.

The system leverages Google's Gemini 2.0 Flash AI model orchestrated through LangGraph workflows to conduct intelligent multi-stage conversations. It asks clarifying questions about your ideal vacation, learns from your responses, and applies this knowledge to suggest destinations that truly match your preferences. Once you've chosen a destination, MyTravelAgent guides you through a comprehensive planning workflow covering accommodations, flights, activities, and itinerary building.

Built for both casual travelers seeking inspiration and serious planners organizing complex trips, MyTravelAgent provides an intuitive interface that makes trip planning feel less like a chore and more like an exciting conversation with a knowledgeable friend. The application handles everything from initial brainstorming to final booking preparation, all while keeping your travel preferences and trip details securely organized in one place.

---

## Key Features

### AI-Powered Destination Discovery
- **Conversational Interface**: Natural language interaction to understand your travel preferences
- **Intelligent Questioning**: AI asks 3-6 targeted clarifying questions to refine recommendations
- **Personalized Recommendations**: Generates exactly 3 tailored destination suggestions based on your input
- **Commitment Detection**: Automatically recognizes when you've decided on a destination
- **Conversation State Management**: Maintains context across multiple sessions

### Comprehensive Trip Management
- **Full CRUD Operations**: Create, view, update, and delete trips with ease
- **Multi-Stage Planning Workflow**: Guided process through destination selection, hotels, flights, activities, and itinerary
- **Trip Status Tracking**: Monitor progress from initial planning through booking to completion
- **Budget Management**: Set and track budgets for each trip
- **Multiple Trip Support**: Manage several trips simultaneously with clear organization

### User Preferences & Personalization
- **Preference Storage**: System remembers your travel style and preferences
- **Budget Ranges**: Define your comfortable spending ranges
- **Group Size Preferences**: Indicate whether you travel solo, as a couple, or in groups
- **Historical Context**: AI learns from your past interactions

### Secure & Scalable Architecture
- **JWT Authentication**: Secure token-based authentication with automatic refresh
- **Rate Limiting**: Protects against abuse with sensible request limits
- **User Data Isolation**: Each user's trips and conversations are completely private
- **Production-Ready**: Deployed on Render.com with PostgreSQL and Redis caching

---

## Tech Stack

### Backend
- **Framework**: Django 4.2.23 with Django REST Framework 3.16.0
- **Language**: Python 3.11
- **Database**: PostgreSQL 15
- **Authentication**: JWT (djangorestframework-simplejwt 5.5.1)
- **AI/ML Stack**:
  - LangChain & LangChain Core (AI framework)
  - LangGraph (workflow orchestration)
  - Google Generative AI (Gemini 2.0 Flash)
  - Pydantic (data validation)
- **API Features**:
  - django-filter 25.1 (filtering & search)
  - django-ratelimit 4.1.0 (rate limiting)
  - django-cors-headers 4.7.0 (CORS support)
- **Production**:
  - Gunicorn 21.2.0 (WSGI server)
  - WhiteNoise 6.6.0 (static file serving)
  - psycopg2-binary (PostgreSQL adapter)

### Frontend
- **Framework**: React 19.1.1
- **Build Tool**: Vite 7.1.2
- **Routing**: React Router DOM 7.8.0
- **HTTP Client**: Axios 1.11.0
- **UI Components**: IBM Carbon Design System v2.72.1
- **Styling**: SASS 1.90.0
- **Token Management**: jwt-decode 4.0.0
- **Code Quality**: ESLint 9.33.0

### Infrastructure
- **Containerization**: Docker & Docker Compose
- **Database**: PostgreSQL 15
- **Caching**: Redis (production) / Database cache (development)
- **Web Server**: Nginx (frontend) / Gunicorn (backend)
- **Deployment**: Render.com

---

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python**: Version 3.11 or higher
- **Node.js**: Version 18 or higher (with npm)
- **PostgreSQL**: Version 15 or higher
- **Docker & Docker Compose**: Latest stable versions (for containerized deployment)
- **Google Generative AI API Key**: Required for AI features ([Get one here](https://ai.google.dev/))

### System Requirements
- **Operating System**: Linux, macOS, or Windows (with WSL recommended)
- **RAM**: Minimum 4GB (8GB recommended for development)
- **Disk Space**: At least 2GB free space

---

## Installation

### Option 1: Docker Setup (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/MyTravelAgent.git
   cd MyTravelAgent
   ```

2. **Set up environment variables**

   Create a `.env` file in the `backend` directory:
   ```bash
   # Backend Environment Variables
   SECRET_KEY=your-secure-secret-key-here
   DEBUG=True
   DATABASE_URL=postgresql://lexc:secretpassw0rd@db:5432/travel_DB
   GOOGLE_API_KEY=your-google-gemini-api-key
   ```

   Create a `.env` file in the `frontend` directory:
   ```bash
   # Frontend Environment Variables
   VITE_API_URL=http://localhost:8000
   ```

3. **Start the application**
   ```bash
   docker-compose up --build
   ```

4. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - Admin Panel: http://localhost:8000/admin

### Option 2: Local Development Setup

#### Backend Setup

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv

   # On macOS/Linux
   source venv/bin/activate

   # On Windows
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up PostgreSQL database**
   ```bash
   # Create database
   createdb travel_DB

   # Or using psql
   psql -U postgres
   CREATE DATABASE travel_DB;
   \q
   ```

5. **Configure environment variables**

   Create `backend/.env`:
   ```bash
   SECRET_KEY=your-secure-secret-key-here
   DEBUG=True
   DATABASE_URL=postgresql://username:password@localhost:5432/travel_DB
   GOOGLE_API_KEY=your-google-gemini-api-key
   ```

6. **Run migrations**
   ```bash
   python manage.py migrate
   python manage.py createcachetable
   ```

7. **Create superuser (optional)**
   ```bash
   python manage.py createsuperuser
   ```

8. **Start development server**
   ```bash
   python manage.py runserver
   ```

#### Frontend Setup

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Configure environment variables**

   Create `frontend/.env`:
   ```bash
   VITE_API_URL=http://localhost:8000
   ```

4. **Start development server**
   ```bash
   npm run dev
   ```

5. **Access the application**
   - Frontend: http://localhost:5173

---

## Usage

### Getting Started

1. **Register an Account**
   - Navigate to http://localhost:5173/register
   - Create your account with a username and password
   - You'll be automatically logged in after registration

2. **Create Your First Trip**
   - Click the "Create New Trip" button on the dashboard
   - Enter a trip title (e.g., "Summer 2025 Vacation")
   - The trip is created in "planning" status

3. **Discover Destinations with AI**
   - Click on your newly created trip
   - You'll be taken to the AI recommendation chat
   - Start by describing your ideal vacation, for example:
     ```
     I want a relaxing beach vacation in Southeast Asia
     with great food and under $2000 for 7 days
     ```

4. **Answer Clarifying Questions**
   - The AI will ask 3-6 targeted questions like:
     - "Do you prefer busy beaches with nightlife or secluded quiet spots?"
     - "Are you interested in water activities like snorkeling or diving?"
     - "How important is easy access to local culture and historical sites?"
   - Answer naturally in your own words

5. **Review Recommendations**
   - After answering questions, the AI generates exactly 3 destination recommendations
   - Each recommendation includes:
     - Destination name and country
     - Detailed description explaining why it matches your preferences
     - Best time to visit
     - Average cost per day
   - Example response:
     ```
     1. Koh Lanta, Thailand
        A laid-back island paradise with pristine beaches, incredible
        seafood, and a relaxed vibe perfect for unwinding...
     ```

6. **Commit to a Destination**
   - Tell the AI which destination you prefer:
     ```
     I love the sound of Koh Lanta! Let's plan this trip there.
     ```
   - The system automatically updates your trip with the chosen destination

7. **Continue Planning**
   - Proceed through the multi-stage planning workflow:
     - Select accommodations
     - Book flights
     - Plan activities
     - Build your itinerary
     - Review and finalize

### API Usage Examples

#### Authentication

```bash
# Register a new user
curl -X POST http://localhost:8000/api/user/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "traveler123",
    "password": "SecurePass123!"
  }'

# Login and get JWT tokens
curl -X POST http://localhost:8000/api/token \
  -H "Content-Type: application/json" \
  -d '{
    "username": "traveler123",
    "password": "SecurePass123!"
  }'

# Response:
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

#### Trip Management

```bash
# Create a new trip
curl -X POST http://localhost:8000/api/trips/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "European Adventure 2025",
    "budget": 5000.00,
    "travelers_count": 2
  }'

# List all your trips
curl -X GET http://localhost:8000/api/trips/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Get specific trip details
curl -X GET http://localhost:8000/api/trips/1/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Update a trip
curl -X PUT http://localhost:8000/api/trips/1/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "European Adventure 2025 - Updated",
    "start_date": "2025-06-15",
    "end_date": "2025-06-30",
    "budget": 6000.00
  }'
```

#### AI Chat Interaction

```bash
# Send a message to the AI
curl -X POST http://localhost:8000/destination_search/chat/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "trip_id": 1,
    "message": "I want a cultural trip to Asia with temples and history"
  }'

# Response:
{
  "response": "That sounds wonderful! To help me suggest the perfect...",
  "conversation_stage": "asking_clarifications",
  "recommendations": null
}

# Get conversation history
curl -X GET http://localhost:8000/destination_search/conversations/1/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Reset conversation
curl -X POST http://localhost:8000/destination_search/conversations/1/reset/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Project Structure

```
MyTravelAgent/
│
├── backend/                          # Django Backend Application
│   ├── api/                         # Main Trip Management App
│   │   ├── migrations/             # Database migrations
│   │   ├── models.py               # Core models (Trip, Destination, UserPreferences)
│   │   ├── views.py                # DRF ViewSets for CRUD operations
│   │   ├── serializers.py          # DRF serializers for API responses
│   │   ├── urls.py                 # API route definitions
│   │   ├── validators.py           # Custom input validators
│   │   ├── decorators.py           # Custom decorators
│   │   └── tests.py                # Comprehensive API tests
│   │
│   ├── destination_search/          # AI Recommendation Engine
│   │   ├── logic/
│   │   │   └── recommendation_engine.py  # LangGraph workflow orchestration
│   │   ├── migrations/
│   │   ├── models.py               # Conversation & message models
│   │   ├── views.py                # Chat API endpoints
│   │   ├── urls.py                 # Chat route definitions
│   │   └── tests.py                # Workflow and AI tests
│   │
│   ├── backend/                     # Django Project Configuration
│   │   ├── settings.py             # Application settings & config
│   │   ├── urls.py                 # Root URL routing
│   │   ├── wsgi.py                 # WSGI configuration
│   │   └── asgi.py                 # ASGI configuration
│   │
│   ├── manage.py                    # Django management CLI
│   ├── requirements.txt             # Python dependencies
│   ├── Dockerfile                   # Docker build configuration
│   └── .env                         # Environment variables (not tracked)
│
├── frontend/                         # React Frontend Application
│   ├── src/
│   │   ├── pages/                  # Main application pages
│   │   │   ├── Home.jsx           # Trip dashboard & list view
│   │   │   ├── RecommendationChat.jsx  # AI chat interface
│   │   │   ├── Login.jsx          # User login page
│   │   │   ├── Register.jsx       # User registration page
│   │   │   └── NotFound.jsx       # 404 error page
│   │   │
│   │   ├── components/             # Reusable React components
│   │   │   ├── Form.jsx           # Auth form component
│   │   │   ├── ProtectedRoute.jsx # JWT authentication wrapper
│   │   │   └── LoadingIndicator.jsx  # Loading state component
│   │   │
│   │   ├── styles/                 # SASS stylesheets
│   │   │   ├── Home.scss
│   │   │   ├── Login.scss
│   │   │   └── RecommendationChat.scss
│   │   │
│   │   ├── App.jsx                 # Main app component & routing
│   │   ├── api.js                  # Axios instance & interceptors
│   │   ├── constants.js            # Application constants
│   │   └── main.jsx                # React app entry point
│   │
│   ├── public/                      # Static assets
│   ├── package.json                 # npm dependencies & scripts
│   ├── vite.config.js              # Vite build configuration
│   ├── Dockerfile                   # Docker build configuration
│   ├── nginx.conf                   # Nginx server configuration
│   └── .env                         # Environment variables (not tracked)
│
├── docker-compose.yml               # Multi-container orchestration
├── .gitignore                       # Git ignore patterns
├── .pre-commit-config.yaml          # Code quality hooks
└── README.md                        # This file
```

### Key Components Explained

#### Backend Architecture

- **`api/models.py`**: Contains the core data models including `Trip`, `Destination`, `UserPreferences`, and `PlanningSession`. These models define the database schema and business logic.

- **`destination_search/logic/recommendation_engine.py`**: The heart of the AI system. Implements a LangGraph state machine with four nodes:
  - `ask_activities`: Initial conversation setup
  - `question_generator`: Creates clarifying questions using Gemini
  - `clarifier`: Processes user responses
  - `destination_generator`: Produces final recommendations

- **`api/views.py`**: DRF ViewSets that handle all CRUD operations with built-in pagination, filtering, and permission checks.

#### Frontend Architecture

- **`App.jsx`**: Defines application routing using React Router, including protected routes that require authentication.

- **`RecommendationChat.jsx`**: The main chat interface that manages conversation state, displays messages, and renders recommendation cards. Includes a progress indicator showing the user's position in the 4-stage discovery workflow.

- **`api.js`**: Configures Axios with JWT token injection and automatic token refresh handling.

---

## API Documentation

### Base URL
- **Development**: `http://localhost:8000`
- **Production**: `https://my-travel-agent.onrender.com`

### Authentication Endpoints

#### Register User
```http
POST /api/user/register
Content-Type: application/json

{
  "username": "string",
  "password": "string"
}

Response: 201 Created
{
  "id": 1,
  "username": "traveler123"
}

Rate Limit: 5 requests per hour
```

#### Login (Get JWT Token)
```http
POST /api/token
Content-Type: application/json

{
  "username": "string",
  "password": "string"
}

Response: 200 OK
{
  "access": "eyJ0eXAiOiJKV1Qi...",  // Valid for 30 minutes
  "refresh": "eyJ0eXAiOiJKV1Qi..."  // Valid for 1 day
}
```

#### Refresh Token
```http
POST /api/token/refresh
Content-Type: application/json

{
  "refresh": "your-refresh-token"
}

Response: 200 OK
{
  "access": "new-access-token"
}
```

### Trip Management Endpoints

#### List Trips
```http
GET /api/trips/
Authorization: Bearer {access_token}

Query Parameters:
  - page: integer (default: 1)
  - status: string (planning, ai_chat_active, booked, etc.)
  - destination: string (search by destination name)
  - search: string (search in title and description)

Response: 200 OK
{
  "count": 25,
  "next": "http://localhost:8000/api/trips/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Summer Vacation 2025",
      "description": "Beach getaway",
      "destination": {
        "id": 1,
        "name": "Koh Lanta",
        "city": "Koh Lanta",
        "country": "Thailand",
        "description": "Beautiful island paradise..."
      },
      "start_date": "2025-06-15",
      "end_date": "2025-06-22",
      "budget": "2000.00",
      "travelers_count": 2,
      "status": "planning",
      "created_at": "2025-01-15T10:30:00Z",
      "updated_at": "2025-01-15T10:30:00Z"
    }
  ]
}

Rate Limit: 100 requests per hour
```

#### Create Trip
```http
POST /api/trips/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "title": "European Adventure",
  "description": "Summer tour of Europe",
  "budget": 5000.00,
  "travelers_count": 2,
  "start_date": "2025-07-01",    // Optional
  "end_date": "2025-07-15"       // Optional
}

Response: 201 Created
{
  "id": 2,
  "title": "European Adventure",
  "status": "planning",
  "destination": null,
  ...
}

Rate Limit: 20 requests per hour
```

#### Get Trip Details
```http
GET /api/trips/{id}/
Authorization: Bearer {access_token}

Response: 200 OK
{
  "id": 1,
  "title": "Summer Vacation 2025",
  ...
}
```

#### Update Trip
```http
PUT /api/trips/{id}/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "title": "Updated Trip Title",
  "budget": 3000.00,
  "status": "booked"
}

Response: 200 OK
```

#### Delete Trip
```http
DELETE /api/trips/{id}/
Authorization: Bearer {access_token}

Response: 204 No Content
```

### Destination Search (AI Chat) Endpoints

#### Send Chat Message
```http
POST /destination_search/chat/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "trip_id": 1,
  "message": "I want a relaxing beach vacation in Southeast Asia"
}

Response: 200 OK
{
  "response": "That sounds wonderful! To give you the best recommendations, I'd like to ask a few questions...",
  "conversation_stage": "asking_clarifications",
  "recommendations": null,
  "message_id": 123
}

// After all questions answered:
{
  "response": "Based on your preferences, here are 3 perfect destinations...",
  "conversation_stage": "destinations_complete",
  "recommendations": [
    {
      "destination_name": "Koh Lanta",
      "country": "Thailand",
      "description": "A laid-back island paradise..."
    },
    {
      "destination_name": "Phu Quoc",
      "country": "Vietnam",
      "description": "Vietnam's largest island..."
    },
    {
      "destination_name": "Langkawi",
      "country": "Malaysia",
      "description": "An archipelago of 99 islands..."
    }
  ]
}

Rate Limit: 10 requests per minute
```

#### Get Conversation History
```http
GET /destination_search/conversations/{trip_id}/
Authorization: Bearer {access_token}

Response: 200 OK
{
  "conversation_id": 1,
  "trip_id": 1,
  "current_stage": "destinations_complete",
  "messages": [
    {
      "id": 1,
      "is_user": true,
      "content": "I want a beach vacation",
      "timestamp": "2025-01-15T10:30:00Z"
    },
    {
      "id": 2,
      "is_user": false,
      "content": "Great! Let me ask a few questions...",
      "timestamp": "2025-01-15T10:30:15Z"
    }
  ],
  "recommendations": [...]
}
```

#### Reset Conversation
```http
POST /destination_search/conversations/{trip_id}/reset/
Authorization: Bearer {access_token}

Response: 200 OK
{
  "message": "Conversation reset successfully"
}
```

### User Preferences Endpoints

#### Get User Preferences
```http
GET /api/user-preferences/
Authorization: Bearer {access_token}

Response: 200 OK
{
  "count": 1,
  "results": [
    {
      "id": 1,
      "preferences_text": "I love beach destinations with good food",
      "budget_min": "1000.00",
      "budget_max": "3000.00",
      "preferred_group_size": 2,
      "created_at": "2025-01-15T10:30:00Z",
      "updated_at": "2025-01-15T10:30:00Z"
    }
  ]
}
```

#### Create/Update Preferences
```http
POST /api/user-preferences/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "preferences_text": "I enjoy cultural experiences and local cuisine",
  "budget_min": 2000.00,
  "budget_max": 5000.00,
  "preferred_group_size": 4
}

Response: 201 Created
```

### Planning Session Endpoints

#### Create Planning Session
```http
POST /api/planning-sessions/
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "trip": 1
}

Response: 201 Created
{
  "id": 1,
  "trip": 1,
  "current_stage": "destination_selection",
  "is_active": true,
  "progress_percentage": 0,
  "stages_completed": []
}
```

#### Advance to Next Stage
```http
POST /api/planning-sessions/{id}/advance_stage/
Authorization: Bearer {access_token}

Response: 200 OK
{
  "message": "Advanced to hotel_planning",
  "current_stage": "hotel_planning",
  "progress_percentage": 14
}
```

#### Get Session Status
```http
GET /api/planning-sessions/{id}/status/
Authorization: Bearer {access_token}

Response: 200 OK
{
  "current_stage": "activity_planning",
  "progress_percentage": 57,
  "is_active": true,
  "stages_completed": [
    "destination_selection",
    "hotel_planning",
    "flight_planning"
  ]
}
```

### Error Responses

All endpoints may return these error responses:

```http
400 Bad Request
{
  "error": "Invalid input data",
  "details": {
    "field_name": ["Error message"]
  }
}

401 Unauthorized
{
  "detail": "Authentication credentials were not provided."
}

403 Forbidden
{
  "detail": "You do not have permission to perform this action."
}

404 Not Found
{
  "detail": "Not found."
}

429 Too Many Requests
{
  "detail": "Request was throttled. Expected available in X seconds."
}

500 Internal Server Error
{
  "error": "An unexpected error occurred"
}
```

---

## Configuration

### Environment Variables

#### Backend Configuration

Create a `.env` file in the `backend/` directory:

```bash
# Django Settings
SECRET_KEY=your-secure-django-secret-key-min-50-chars
DEBUG=True                           # Set to False in production

# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/travel_DB

# Google Gemini AI
GOOGLE_API_KEY=your-google-gemini-api-key-here

# Optional: Redis Cache (recommended for production)
REDIS_URL=redis://localhost:6379/0

# Security (Production)
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://yourfrontend.com

# JWT Token Settings (optional, defaults provided)
ACCESS_TOKEN_LIFETIME_MINUTES=30
REFRESH_TOKEN_LIFETIME_DAYS=1
```

#### Frontend Configuration

Create a `.env` file in the `frontend/` directory:

```bash
# API Backend URL
VITE_API_URL=http://localhost:8000   # Development
# VITE_API_URL=https://your-backend.onrender.com  # Production
```

### Django Settings Overview

Key configuration areas in `backend/backend/settings.py`:

- **Database**: Uses `dj-database-url` to parse `DATABASE_URL`
- **Caching**: Redis in production, database cache in development
- **Static Files**: WhiteNoise for serving in production
- **CORS**: Configured for localhost:5173 (dev) and production domains
- **JWT**: 30-minute access tokens, 1-day refresh tokens
- **Rate Limiting**: Per-endpoint limits defined in views
- **Security**: HTTPS redirect, HSTS, secure cookies in production

### Customizing AI Behavior

The AI recommendation engine can be customized in `backend/destination_search/logic/recommendation_engine.py`:

```python
# Number of clarifying questions (default: 3-6)
MIN_QUESTIONS = 3
MAX_QUESTIONS = 6

# Number of destination recommendations (default: 3)
NUM_RECOMMENDATIONS = 3

# AI Model configuration
model = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp",
    google_api_key=settings.GOOGLE_API_KEY,
    temperature=0.7  # Adjust for creativity vs. consistency
)
```

### Rate Limiting Configuration

Modify rate limits in `backend/api/views.py`:

```python
@ratelimit(key='user', rate='100/h', method='GET')  # Trip listing
@ratelimit(key='user', rate='20/h', method='POST')   # Trip creation
```

---

## Testing

### Backend Tests

The project includes comprehensive test suites for all major components.

#### Running All Tests

```bash
cd backend
python manage.py test
```

#### Running Specific Test Modules

```bash
# Test API endpoints
python manage.py test api.tests

# Test AI recommendation engine
python manage.py test destination_search.tests

# Test with coverage report
coverage run --source='.' manage.py test
coverage report
coverage html  # Generates HTML report in htmlcov/
```

#### Test Coverage

The test suite includes:

- **Authentication Tests**: Registration, login, token refresh, permission checks
- **Trip CRUD Tests**: Create, read, update, delete operations with user isolation
- **Rate Limiting Tests**: Verify throttling behavior
- **AI Workflow Tests**: LangGraph state machine transitions
- **Conversation Tests**: Message persistence, state management
- **Recommendation Tests**: Destination generation and parsing
- **Validation Tests**: Input sanitization and custom validators
- **Planning Session Tests**: Stage advancement and progress tracking

Example test output:
```bash
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
..............................................................
----------------------------------------------------------------------
Ran 62 tests in 15.432s

OK
```

### Frontend Tests

The frontend currently uses ESLint for code quality:

```bash
cd frontend
npm run lint
```

To add unit tests (recommended for production):

```bash
# Install testing libraries
npm install --save-dev vitest @testing-library/react @testing-library/jest-dom

# Run tests
npm run test
```

### Integration Testing

Test the full stack locally:

1. Start services with Docker Compose:
   ```bash
   docker-compose up
   ```

2. Run backend tests in container:
   ```bash
   docker-compose exec backend python manage.py test
   ```

3. Test API endpoints manually:
   ```bash
   # Register user
   curl -X POST http://localhost:8000/api/user/register \
     -H "Content-Type: application/json" \
     -d '{"username":"testuser","password":"TestPass123!"}'

   # Create trip
   curl -X POST http://localhost:8000/api/trips/ \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"title":"Test Trip","budget":1000}'
   ```

### Pre-commit Hooks

The project uses pre-commit hooks for code quality. Install them:

```bash
pip install pre-commit
pre-commit install
```

Hooks include:
- Trailing whitespace removal
- End-of-file fixer
- YAML syntax checking
- Large file prevention

---

## Contributing

We welcome contributions to MyTravelAgent! Here's how you can help:

### Getting Started

1. **Fork the repository**
   ```bash
   git clone https://github.com/yourusername/MyTravelAgent.git
   cd MyTravelAgent
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Set up your development environment**
   - Follow the [Installation](#installation) instructions
   - Install pre-commit hooks: `pre-commit install`

### Development Workflow

1. **Make your changes**
   - Write clean, documented code
   - Follow existing code style and patterns
   - Add tests for new features

2. **Test your changes**
   ```bash
   # Backend tests
   cd backend
   python manage.py test

   # Frontend linting
   cd frontend
   npm run lint
   ```

3. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: Add your feature description"
   ```

   Use conventional commit messages:
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation changes
   - `test:` Adding tests
   - `refactor:` Code refactoring
   - `style:` Formatting changes

4. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Create a Pull Request**
   - Go to the original repository on GitHub
   - Click "New Pull Request"
   - Describe your changes thoroughly
   - Reference any related issues

### Code Style Guidelines

#### Python (Backend)
- Follow PEP 8 style guide
- Use type hints where appropriate
- Write docstrings for classes and functions
- Keep functions focused and under 50 lines when possible
- Use Django best practices

Example:
```python
def calculate_trip_cost(trip: Trip, days: int) -> Decimal:
    """
    Calculate the total estimated cost for a trip.

    Args:
        trip: Trip instance with destination and travelers_count
        days: Number of days for the trip

    Returns:
        Decimal: Total estimated cost
    """
    daily_cost = trip.destination.average_cost_per_day
    return daily_cost * days * trip.travelers_count
```

#### JavaScript (Frontend)
- Use ES6+ features
- Prefer functional components with hooks
- Use meaningful variable and function names
- Keep components under 200 lines
- Add PropTypes or TypeScript types

Example:
```jsx
const TripCard = ({ trip, onSelect }) => {
  const formattedBudget = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(trip.budget);

  return (
    <div className="trip-card" onClick={() => onSelect(trip.id)}>
      <h3>{trip.title}</h3>
      <p>Budget: {formattedBudget}</p>
    </div>
  );
};
```

### Areas for Contribution

We especially welcome contributions in these areas:

- **Frontend Testing**: Add unit tests with Vitest
- **Additional AI Models**: Support for Claude, GPT-4, etc.
- **Mobile Responsiveness**: Improve mobile UI/UX
- **Internationalization**: Add i18n support
- **Performance Optimization**: Database query optimization, caching
- **Documentation**: Improve API docs, add tutorials
- **Accessibility**: WCAG compliance improvements
- **New Features**:
  - Calendar integration
  - Budget tracking charts
  - Social features (share trips)
  - Trip collaboration
  - Export to PDF

### Reporting Bugs

When reporting bugs, please include:

1. **Description**: Clear description of the issue
2. **Steps to Reproduce**: Numbered list of steps
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**:
   - OS and version
   - Python version
   - Node.js version
   - Browser (for frontend issues)
6. **Screenshots**: If applicable
7. **Error Messages**: Complete error messages and stack traces

### Questions and Discussion

- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Discussions**: Use GitHub Discussions for questions and ideas
- **Email**: Contact the maintainers directly for sensitive issues

---

## License

This project does not currently have a specified license. Please contact the repository owner for usage permissions and licensing information.

If you're planning to use this project, we recommend adding a license such as:
- **MIT License**: Permissive, allows commercial use
- **Apache 2.0**: Permissive with patent protection
- **GPL v3**: Copyleft, requires derivative works to be open source

---

## Contact & Author Information

### Project Maintainer
- **GitHub**: [@lexc24](https://github.com/lexc24)
- **Repository**: [MyTravelAgent](https://github.com/lexc24/MyTravelAgent)

### Project Links
- **Live Demo**: https://my-travel-agent.onrender.com (if deployed)
- **API Documentation**: See [API Documentation](#api-documentation) section above
- **Issue Tracker**: [GitHub Issues](https://github.com/lexc24/MyTravelAgent/issues)

### Getting Help

If you need assistance:

1. **Check Documentation**: Review this README and inline code documentation
2. **Search Issues**: Look through existing GitHub Issues
3. **Ask Questions**: Open a GitHub Discussion
4. **Report Bugs**: Create a new GitHub Issue with detailed information
5. **Contact**: Reach out via GitHub profile for urgent matters

### Acknowledgments

This project uses the following open-source technologies:
- **Django** and **Django REST Framework** - Backend framework
- **React** - Frontend library
- **LangChain** and **LangGraph** - AI workflow orchestration
- **Google Gemini** - AI language model
- **IBM Carbon Design System** - UI components
- **PostgreSQL** - Database
- **Docker** - Containerization

Special thanks to all contributors and the open-source community.

---

## System Architecture Overview

For users and customers wanting to understand how MyTravelAgent works:

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│                    (React + IBM Carbon)                         │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   Dashboard  │  │   AI Chat    │  │  Trip Plans  │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/REST API
                             │ (JWT Authentication)
┌────────────────────────────┴────────────────────────────────────┐
│                     Django REST API Layer                       │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   Trips API  │  │   Chat API   │  │  User API    │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                  Business Logic Layer                           │
│                                                                 │
│  ┌──────────────────────────┐  ┌──────────────────────────┐   │
│  │   Trip Management        │  │  AI Workflow Engine      │   │
│  │   • CRUD Operations      │  │  • LangGraph State       │   │
│  │   • Status Tracking      │  │  • Question Generation   │   │
│  │   • Planning Workflow    │  │  • Recommendation AI     │   │
│  └──────────────────────────┘  └──────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────────┐
│                      Data Layer                                 │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  PostgreSQL  │  │    Redis     │  │  Google AI   │        │
│  │  (Trips,     │  │  (Caching)   │  │  (Gemini)    │        │
│  │  Users, etc) │  │              │  │              │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

### How a Trip is Planned (User Journey)

1. **Registration & Login**
   - User creates account with secure JWT authentication
   - Credentials stored securely with Django's authentication system

2. **Trip Creation**
   - User clicks "Create New Trip"
   - Enters basic information (title, budget, travelers)
   - Trip starts in "planning" status

3. **AI Conversation (The Magic Happens Here)**
   - User describes their ideal vacation in natural language
   - AI processes the description and generates 3-6 clarifying questions
   - User answers questions naturally
   - AI uses LangGraph workflow to:
     - Accumulate user preferences
     - Refine understanding with each answer
     - Generate exactly 3 personalized destination recommendations
   - User reviews destinations and chooses one

4. **Destination Selection**
   - When user commits (e.g., "Let's go to Bali!"), the system:
     - Creates a Destination record in the database
     - Links it to the Trip
     - Updates trip status to "destinations_selected"

5. **Planning Workflow**
   - User proceeds through stages:
     - Hotel planning
     - Flight planning
     - Activity planning
     - Itinerary building
   - Each stage tracks progress and completion

6. **Booking & Travel**
   - User marks trip as "booked" when ready
   - After travel dates, status updates to "completed"

### AI Workflow Explained Simply

The AI recommendation engine works like a knowledgeable travel agent:

1. **Listening**: You tell it what you want
2. **Clarifying**: It asks smart follow-up questions
3. **Understanding**: It builds a complete picture of your preferences
4. **Recommending**: It suggests 3 perfect destinations
5. **Learning**: Your preferences are saved for future trips

The system uses Google's Gemini AI model, orchestrated through LangGraph, which is like a flowchart for AI conversations. This ensures the AI stays focused, asks relevant questions, and always provides exactly 3 high-quality recommendations.

### Security & Privacy

- **Your data is yours**: Each user's trips and conversations are completely isolated
- **Secure authentication**: Industry-standard JWT tokens
- **Rate limiting**: Prevents abuse and ensures fair usage
- **HTTPS in production**: All data encrypted in transit
- **No third-party sharing**: Your travel plans stay private

---

## Roadmap

Future enhancements planned for MyTravelAgent:

- [ ] **Mobile App**: Native iOS and Android applications
- [ ] **Trip Collaboration**: Invite friends to plan together
- [ ] **Budget Tracking**: Real-time expense tracking during trips
- [ ] **Calendar Integration**: Sync with Google Calendar, iCal
- [ ] **Flight & Hotel Booking**: Direct booking integration
- [ ] **Photo Gallery**: Upload and organize trip photos
- [ ] **Social Features**: Share trips, view friends' travel plans
- [ ] **AI Enhancements**: Support for multiple AI models, voice input
- [ ] **Offline Mode**: Plan trips without internet connection
- [ ] **Export Options**: PDF itineraries, shareable links
- [ ] **Analytics Dashboard**: Travel statistics and insights

---

**Happy Traveling!** 🌍✈️🏖️

*Built with ❤️ using Django, React, and AI*
