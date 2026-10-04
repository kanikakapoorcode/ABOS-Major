# ABOS — Local Setup Guide

Step-by-step guide to get ABOS running on your machine from scratch.

---

## Prerequisites

Install these before starting:

| Tool | Version | Install |
|---|---|---|
| Python | 3.12+ | https://python.org |
| Poetry | Latest | https://python-poetry.org/docs/#installation |
| Node.js | 20+ | https://nodejs.org |
| Docker Desktop | Latest | https://docker.com/products/docker-desktop |
| Git | Latest | https://git-scm.com |

Verify:
```bash
python --version       # should say 3.12.x
poetry --version
node --version         # should say v20.x or higher
docker --version
```

---

## Step 1 — Get the Code

```bash
git clone https://github.com/your-org/abos.git
cd abos
```

---

## Step 2 — Environment Variables

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in:

```env
# Pick one LLM provider and add the key
ACTIVE_LLM=gemini/gemini-1.5-pro
GEMINI_API_KEY=AIza...your-key-here...

# Leave DB and Redis as-is if using Docker (default values match docker-compose.yml)
DATABASE_URL=postgresql+asyncpg://abos_user:abos_password@localhost:5432/abos
REDIS_URL=redis://localhost:6379/0

# Generate two random strings for JWT (use a password manager or run: python -c "import secrets; print(secrets.token_hex(32))")
APP_SECRET_KEY=...
JWT_SECRET_KEY=...
```

**Never share your `.env` file or commit it to Git.**

---

## Step 3 — Start Infrastructure (PostgreSQL + Redis)

```bash
docker-compose up -d postgres redis
```

This starts:
- PostgreSQL on port `5432`
- Redis on port `6379`

Verify they are running:
```bash
docker-compose ps
```

Both should show `running`.

---

## Step 4 — Install Python Dependencies

```bash
poetry install
```

This reads `pyproject.toml` and installs everything into a virtual environment managed by Poetry.

---

## Step 5 — Run Database Migrations

```bash
poetry run alembic upgrade head
```

This creates all tables in PostgreSQL. You should see output like:
```
INFO  [alembic.runtime.migration] Running upgrade  -> abc123, initial schema
```

If you see errors, check that PostgreSQL is running and `DATABASE_URL` in `.env` is correct.

---

## Step 6 — Enable pgvector Extension

Connect to the database and enable the pgvector extension (only needed once):

```bash
docker exec -it abos_postgres psql -U abos_user -d abos -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

---

## Step 7 — Start the Backend

```bash
poetry run uvicorn backend.main:app --reload --port 8000
```

Open http://localhost:8000/api/docs — you should see the ABOS API docs.

---

## Step 8 — Start the Celery Worker

Open a **new terminal** and run:

```bash
poetry run celery -A backend.workers.celery_app worker --loglevel=info
```

Keep this running while you develop. Celery handles background agent execution tasks.

---

## Step 9 — Start the Frontend

Open another **new terminal**:

```bash
cd frontend
npm install      # first time only
npm run dev
```

Open http://localhost:5173 — you should see the ABOS dashboard.

---

## Step 10 — Start MLflow (optional but recommended)

```bash
poetry run mlflow ui --port 5000
```

Open http://localhost:5000 to view experiment tracking.

---

## You Now Have

| Service | URL |
|---|---|
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/api/docs |
| Frontend Dashboard | http://localhost:5173 |
| MLflow | http://localhost:5000 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

## Full Docker Stack (Alternative)

If you want to run everything in Docker (no local Python/Node needed):

```bash
docker-compose up --build
```

This starts all services. Note: hot-reload won't work in this mode — use the step-by-step approach above during development.

---

## Common Problems

### "Connection refused" on port 5432
PostgreSQL isn't running. Run: `docker-compose up -d postgres`

### "poetry: command not found"
Poetry isn't installed or isn't in your PATH. Follow: https://python-poetry.org/docs/#installation

### "alembic: No module named backend"
Run alembic from the project root (where `alembic.ini` is), not from inside `backend/`.

### LLM calls return 401 / 403
Your API key is wrong or missing. Check `GEMINI_API_KEY` or `OPENAI_API_KEY` in `.env`.

### Frontend shows blank page or "Network Error"
Make sure the backend is running on port 8000. Check `VITE_API_BASE_URL` in `.env`.

### pgvector error: "type vector does not exist"
Run the pgvector extension command from Step 6.

---

## Keeping Dependencies Up to Date

```bash
# Add a new Python package
poetry add package-name

# Add a dev-only package
poetry add --group dev package-name

# Add a frontend package
cd frontend && npm install package-name
```

Always commit both `pyproject.toml` + `poetry.lock` (Python) and `package.json` + `package-lock.json` (frontend) together.
