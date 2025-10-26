# ADR-005: Docker Development Environment

## Context

We needed a development environment that:
- Works consistently across team members (Mac, Windows, Linux)
- Mirrors production configuration (same Python/Node/Postgres versions)
- Starts with one command (`docker-compose up`)
- Supports hot reload (code changes reflect immediately)
- Isolates dependencies (no conflicts with other projects)
- Easy onboarding for new developers

## Decision

We chose **Docker Compose** for local development with:
- Three services: `db` (PostgreSQL 15), `backend` (Django), `frontend` (React + Vite)
- Volume mounts for hot reload (`./backend:/app`, `./frontend:/app`)
- Named volume for database persistence (`postgres_data`)
- Shared network for inter-service communication
- Environment variables for configuration (`.env` files)

## Why This Approach

### Docker Compose vs. Manual Setup

**Manual Setup (rejected):**
```bash
# Developer must install:
brew install python@3.11   # or apt-get, or download installer
brew install postgresql@15
brew install node@18
pip install -r requirements.txt
npm install
createdb travel_DB
python manage.py migrate
python manage.py runserver &
npm run dev &
```

**Problems:**
- ❌ Version conflicts (developer has Python 3.9, project needs 3.11)
- ❌ "Works on my machine" (different Postgres versions, different Node versions)
- ❌ Onboarding takes hours (install tools, debug conflicts, read setup docs)
- ❌ Pollutes global environment (pip packages conflict with other projects)

**Docker Compose Solution:**
```bash
docker-compose up
# Done. All services running, all dependencies installed, all versions correct.
```

**Benefits:**
- ✅ One command to start everything
- ✅ Consistent versions (Python 3.11, Postgres 15, Node 18)
- ✅ Isolated environment (no conflicts with other projects)
- ✅ Onboarding takes minutes (install Docker, run `docker-compose up`)

---

### Docker Compose vs. Kubernetes (Local)

**Kubernetes (rejected for local dev):**
- ❌ Overkill for 3 services
- ❌ Complex setup (minikube, kubectl, YAML hell)
- ❌ Resource-intensive (runs full K8s cluster locally)
- ❌ Slower startup (30+ seconds)

**Docker Compose wins for local dev:**
- ✅ Simple YAML (`docker-compose.yml` is 30 lines)
- ✅ Fast startup (5-10 seconds)
- ✅ Good enough for development

**When to Use Kubernetes:**
- Production (we use Render, not K8s)
- If we had 50+ microservices (we have 3 services)
- If we needed auto-scaling, service mesh, etc.

---

## Integration Impact

### docker-compose.yml Structure

File: `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:15                        # Official Postgres 15 image
    volumes:
      - postgres_data:/var/lib/postgresql/data/   # Persistent storage
    environment:
      POSTGRES_DB: travel_DB
      POSTGRES_USER: lexc
      POSTGRES_PASSWORD: secretpassw0rd
    ports:
      - "5432:5432"                          # Expose to host (for DB clients)

  backend:
    build: ./backend                         # Build from Dockerfile in ./backend/
    command: >
      sh -c "
      python manage.py migrate &&            # Run migrations on startup
      python manage.py createcachetable &&   # Create cache table (if using DB cache)
      python manage.py runserver 0.0.0.0:8000
      "
    volumes:
      - ./backend:/app                       # Mount local code → hot reload
    ports:
      - "8000:8000"                          # Expose Django API
    depends_on:
      - db                                   # Wait for DB to start first
    environment:
      - DEBUG=1                              # Enable debug mode
      - DATABASE_URL=postgresql://lexc:secretpassw0rd@db:5432/travel_DB

  # Frontend omitted from docker-compose (run manually: npm run dev)
  # Why? Vite dev server is faster outside Docker (HMR works better)

volumes:
  postgres_data:                             # Named volume (persists between runs)
```

---

### Key Design Decisions

**1. Automatic Migrations on Startup**

```yaml
command: >
  sh -c "
  python manage.py migrate &&
  python manage.py runserver 0.0.0.0:8000
  "
```

**Why:**
- ✅ New developer runs `docker-compose up` → migrations run automatically
- ✅ No need to remember `docker-compose exec backend python manage.py migrate`
- ✅ Ensures database schema is always up-to-date

**Trade-off:**
- ❌ Adds 2-5 seconds to startup
- ❌ If migrations fail, backend won't start
- **Accepted**: Better to fail fast than run with stale schema

---

**2. Volume Mounts for Hot Reload**

```yaml
volumes:
  - ./backend:/app   # Local ./backend directory mounted to /app in container
```

**How It Works:**
```
Developer edits: ./backend/api/views.py
    ↓
Docker sees file change in mounted volume
    ↓
Django dev server detects change
    ↓
Auto-reloads (without restarting container)
```

**Why This Matters:**
- ✅ Edit code → See changes immediately (no rebuild needed)
- ✅ Same workflow as non-Docker development
- ✅ Fast iteration (no 30-second rebuild for every change)

**Alternative (rejected):**
```yaml
# Copy code into image (no volume mount)
COPY ./backend /app
```

**Problem**: Every code change requires:
```bash
docker-compose build backend   # Rebuild image (30 seconds)
docker-compose up backend      # Restart container
```

---

**3. Named Volume for Database Persistence**

```yaml
volumes:
  postgres_data:   # Named volume (managed by Docker)
```

**Why Named Volume:**
- ✅ Data persists across `docker-compose down`
- ✅ Data persists across computer restarts
- ✅ Managed by Docker (no manual path management)

**Behavior:**
```bash
docker-compose up       # Start services, use existing postgres_data
docker-compose down     # Stop services, postgres_data remains
docker-compose up       # Restart, postgres_data still has data

# To wipe database:
docker-compose down -v  # Delete volumes
docker-compose up       # Fresh database
```

**Alternative (rejected):**
```yaml
volumes:
  - ./postgres_data:/var/lib/postgresql/data  # Host directory mount
```

**Problem:**
- ❌ Permission issues on Windows/Mac (Docker Desktop uses VM)
- ❌ Host path pollution (extra directory in project root)
- ❌ Not portable (path might not exist on other machines)

---

**4. Service Dependencies**

```yaml
backend:
  depends_on:
    - db   # Backend waits for db to start first
```

**What This Does:**
- Docker Compose starts `db` before `backend`
- Backend won't start until `db` container is running

**What This DOESN'T Do:**
- ❌ Doesn't wait for Postgres to be **ready** (just started)
- Backend might fail with "connection refused" if Postgres isn't ready yet

**Better Solution (future):**
```yaml
backend:
  depends_on:
    db:
      condition: service_healthy   # Wait for health check
```

**Postgres Health Check:**
```yaml
db:
  healthcheck:
    test: ["CMD", "pg_isready", "-U", "lexc"]
    interval: 5s
    timeout: 5s
    retries: 5
```

---

**5. Port Mapping**

```yaml
ports:
  - "8000:8000"   # Host port 8000 → Container port 8000
```

**Why Expose Ports:**
- Frontend needs to call backend API (`http://localhost:8000/api/trips/`)
- Developer needs to access Django admin (`http://localhost:8000/admin/`)
- DB clients (DBeaver, pgAdmin) need to connect (`localhost:5432`)

**Security Note:**
- Exposed ports are only accessible on localhost (not public internet)
- Production uses reverse proxy (Nginx, Render's load balancer)

---

### Dockerfile (Backend)

File: `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run server (overridden by docker-compose.yml command)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

**Why `python:3.11-slim`:**
- ✅ Official Python image (well-maintained)
- ✅ `-slim` variant (smaller size: 150 MB vs 1 GB)
- ✅ Debian-based (familiar package manager: apt-get)

**Why `--no-cache-dir`:**
- Reduces image size (pip doesn't cache downloaded packages)
- Important for production (smaller images = faster deploys)

---

### Dockerfile (Frontend - Production Only)

File: `frontend/Dockerfile` (multi-stage build)

```dockerfile
# Stage 1: Build React app
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build    # Creates ./dist folder

# Stage 2: Serve with Nginx
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Why Multi-Stage:**
- ✅ Stage 1 installs Node, builds app (large image: 500 MB)
- ✅ Stage 2 only copies built files to Nginx (small image: 50 MB)
- ✅ Final image doesn't include Node, npm, source code (security + size)

**Why Not in docker-compose.yml:**
- Vite dev server is faster outside Docker (native HMR)
- Developers run `npm run dev` on host, not in container
- Dockerfile is for production (Render deployment)

---

## Code References

**Docker Compose:**
- `docker-compose.yml` - Service definitions, volumes, networks

**Dockerfiles:**
- `backend/Dockerfile` - Django production image
- `frontend/Dockerfile` - React production image (multi-stage build)

**Nginx Config:**
- `frontend/nginx.conf` - Serves React app, proxies API requests

---

## Future Considerations

### 1. Add Health Checks

**Current**: `depends_on` only waits for container to start.

**Future**:
```yaml
db:
  healthcheck:
    test: ["CMD", "pg_isready", "-U", "lexc"]
    interval: 5s
    retries: 5

backend:
  depends_on:
    db:
      condition: service_healthy   # Wait for health check to pass
```

**Benefits:**
- ✅ Backend won't start until Postgres is ready
- ✅ Eliminates "connection refused" errors on first startup

---

### 2. Docker Compose Profiles

**Current**: All services start on `docker-compose up`.

**Future**: Optional services via profiles.

```yaml
services:
  db:
    profiles: ["full"]

  backend:
    profiles: ["full"]

  redis:
    image: redis:7
    profiles: ["full", "cache"]   # Only start if cache needed
```

**Usage:**
```bash
docker-compose --profile full up        # Start all services
docker-compose --profile cache up       # Start only Redis + dependencies
```

**When to Use:**
- If we add Redis, Celery, Elasticsearch (not always needed)
- Speed up startup for developers who only need backend

---

### 3. Separate docker-compose Files

**Current**: One `docker-compose.yml` for everything.

**Future**: Split by environment.

```bash
docker-compose.yml           # Base config (shared)
docker-compose.dev.yml       # Development overrides (volume mounts, debug)
docker-compose.prod.yml      # Production overrides (no volume mounts, optimization)
```

**Usage:**
```bash
# Development
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up
```

**Benefits:**
- ✅ DRY principle (shared config in base file)
- ✅ Environment-specific overrides (dev needs volume mounts, prod doesn't)

---

### 4. BuildKit for Faster Builds

**Current**: Standard Docker build (slow).

**Future**: Enable BuildKit (faster, better caching).

```bash
# Enable BuildKit
export DOCKER_BUILDKIT=1

# Build with cache mounts
docker build --cache-from=myapp:latest .
```

**Benefits:**
- ✅ Parallel builds (build stages in parallel)
- ✅ Better cache invalidation (only rebuild changed layers)
- ✅ Faster CI/CD (reuse layers from previous builds)

---

## Lessons Learned

**What Worked Well:**
- One command to start everything (`docker-compose up`)
- Volume mounts for hot reload (no rebuild needed for code changes)
- Named volumes for database persistence (data survives restarts)
- Automatic migrations on startup (new developers get up-to-date schema)

**What We'd Do Differently:**
- Add health checks sooner (prevent "connection refused" errors)
- Use multi-stage builds for backend (reduce image size)
- Add Docker Compose profiles (optional services like Redis)
- Document common commands (`docker-compose logs`, `docker-compose exec`, etc.)

**Biggest Surprise:**
- Docker Compose is fast enough (no need for Kubernetes in local dev)
- Volume mounts "just work" (no performance issues on Mac/Windows)
- Developers adapted quickly (no resistance to Docker)

**Common Pitfalls:**
- Forgetting to run `docker-compose down -v` when testing migrations (stale DB state)
- Port conflicts (5432 already in use by local Postgres)
- Not enough RAM for Docker Desktop (4 GB minimum, 8 GB recommended)

---

## Interview Talking Point

> "We use Docker Compose for local development to ensure consistency across team members. One command (`docker-compose up`) starts PostgreSQL, Django, and all dependencies with the exact versions we use in production.
>
> Volume mounts enable hot reload—developers edit code and see changes immediately without rebuilding containers. This gives us the isolation and consistency of Docker with the iteration speed of native development.
>
> Named volumes persist database data across restarts, so developers don't lose their test data. Automatic migrations on startup ensure everyone's database schema is always up-to-date.
>
> For production, we use multi-stage Docker builds to create minimal images (50 MB React + Nginx, 150 MB Django). This keeps deploy times fast and reduces attack surface."

---

**Related ADRs:**
- [ADR-001: Django REST Framework](./001-django-rest-framework-choices.md)
- [ADR-004: PostgreSQL Schema Design](./004-postgresql-schema-design.md)
