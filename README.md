# MyTravelAgent

> AI-powered travel planning platform that turns vacation ideas into personalized destination recommendations

[![Live Demo](https://img.shields.io/badge/demo-live-success)](https://my-travel-agent.onrender.com) [![API Docs](https://img.shields.io/badge/API-Swagger-blue)](https://mytravelagent.onrender.com/api/docs) [![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/) [![Django 4.2](https://img.shields.io/badge/Django-4.2-green.svg)](https://www.djangoproject.com/)

**[Live Demo](https://my-travel-agent.onrender.com)** | **[API Documentation](https://mytravelagent.onrender.com/api/docs)** | **[ReDoc](https://mytravelagent.onrender.com/api/redoc)**

---

## Tech Stack

**Backend:** Django REST Framework, PostgreSQL, LangGraph, Google Gemini AI  
**Frontend:** React 19, Vite, IBM Carbon Design System  
**Infrastructure:** Docker, GitHub Actions CI/CD, Render  
**Testing:** pytest, Django TestCase, 85%+ code coverage  
**Security:** JWT authentication, rate limiting, input validation

---

## Key Features

- **RESTful API** with JWT authentication, automatic token refresh, and comprehensive OpenAPI documentation
- **Conversational AI** that asks clarifying questions and generates 3 personalized destination recommendations
- **Multi-stage planning workflow** tracking trips from initial idea through booking
- **CI/CD pipeline** with automated testing, linting, and continuous deployment to production
- **Containerized deployment** with Docker Compose for consistent dev/prod environments
- **Rate-limited endpoints** (5 registration attempts/hour, 10 chat messages/minute)

---

## Quick Start

### Docker Setup (Recommended)
```bash
# Clone and start
git clone https://github.com/yourusername/MyTravelAgent.git
cd MyTravelAgent
docker-compose up --build

# Access:
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/api/docs
```

**Requirements:** Docker, Docker Compose, Google Gemini API key

Set environment variables in `backend/.env`:
```bash
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@db:5432/travel_DB
GOOGLE_API_KEY=your-gemini-api-key
```

### Local Setup (without Docker)
```bash
# Backend
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && python manage.py migrate && python manage.py runserver

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

---

## Architecture

**Workflow:** User describes vacation → AI asks clarifying questions → generates 3 tailored destinations → user selects → proceeds through booking workflow.
```
┌─────────────┐
│ React       │ ← User interacts with chat interface
│ Frontend    │
└──────┬──────┘
       │ HTTP/REST (JWT)
┌──────▼──────────────────────┐
│ Django REST API             │
│ • Trip CRUD endpoints       │
│ • Chat message handling     │
│ • JWT auth + rate limiting  │
└──────┬──────────────────────┘
       │
┌──────▼──────────────────────┐
│ LangGraph AI Workflow       │ ← Orchestrates conversation
│ • Question generation       │
│ • User response processing  │
│ • Destination recommendations│
└──────┬──────────────────────┘
       │
┌──────▼──────────────────────┐
│ PostgreSQL + Google Gemini  │
│ • Trip/user data storage    │
│ • AI model (Gemini 2.0)     │
└─────────────────────────────┘
```

---

## API Documentation

**📘 Full Interactive Docs:** [Swagger UI](https://mytravelagent.onrender.com/api/docs) | [ReDoc](https://mytravelagent.onrender.com/api/redoc)

The API provides:
- **Authentication:** User registration, JWT login with automatic token refresh
- **Trip Management:** Full CRUD operations with filtering, pagination, and search
- **AI Chat:** Conversational interface for destination recommendations
- **Rate Limiting:** Protects endpoints from abuse (5 registrations/hour, 10 chat messages/minute)
- **Comprehensive Docs:** Request/response examples, authentication flows, error handling

All endpoints include OpenAPI specifications with interactive testing capabilities.

---

## Contact

**GitHub:** [@lexc24](https://github.com/lexc24)  
**Live Demo:** [my-travel-agent.onrender.com](https://my-travel-agent.onrender.com)  
**API Docs:** [Swagger](https://mytravelagent.onrender.com/api/docs) | [ReDoc](https://mytravelagent.onrender.com/api/redoc)

---

*Built with Django REST Framework, React, LangGraph, and Google Gemini AI*
