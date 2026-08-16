# ABOS — Adaptive Business Operating System

**An Adaptive Multi-Agent Framework for Goal-Driven Business Workflow Automation**

> Major Project | B.Tech | 2025–2026
> Kanika Kapoor · Ashmit Bhandari · Kaushal Thakur · Harshit Gahlot

---

## What is ABOS?

ABOS takes a high-level business goal (e.g. *"Run a Q4 outreach campaign targeting enterprise leads with low engagement"*) and automatically:

1. **Decomposes it** into a multi-step, multi-department workflow
2. **Routes each step** to a specialized department agent (Sales / Customer Support / Research & Analytics) using a performance-based scheduler
3. **Executes the workflow** via LangGraph-orchestrated agents
4. **Learns from feedback** via a Level-2 explicit-feedback memory layer that improves future routing

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Getting Started (Local)](#getting-started-local)
- [Environment Variables](#environment-variables)
- [Running the Backend](#running-the-backend)
- [Running the Frontend](#running-the-frontend)
- [Database & Migrations](#database--migrations)
- [Agent System](#agent-system)
- [Scheduler](#scheduler)
- [Memory Layer](#memory-layer)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Experiment Tracking (MLflow)](#experiment-tracking-mlflow)
- [Docker (Local Full Stack)](#docker-local-full-stack)
- [Cloud Deployment](#cloud-deployment)
- [Team Responsibilities](#team-responsibilities)
- [Research Positioning](#research-positioning)

---

## Architecture Overview

```
User submits goal (REST API)
        │
        ▼
  FastAPI Backend
        │
        ▼
  Celery Worker  ──────────────────────────────────────────┐
        │                                                   │
        ▼                                                   │
  LangGraph Graph                                          Redis
        │                                                   │
   ┌────┴─────────────────────────────────┐                │
   │                                      │                │
   ▼                                      ▼                │
Goal Planner Node              Performance Scheduler       │
(LLM decomposes goal           (routes steps to best       │
 into workflow steps)           available agent)           │
        │                              │                   │
        ▼                              ▼                   │
┌───────────────────────────────────────────────┐         │
│           Department Agents                    │         │
│  ┌─────────┐  ┌───────────┐  ┌────────────┐  │         │
│  │  Sales  │  │  Support  │  │  Research  │  │         │
│  │  Agent  │  │   Agent   │  │   Agent    │  │         │
│  └─────────┘  └───────────┘  └────────────┘  │         │
└───────────────────────────────────────────────┘         │
        │                                                   │
        ▼                                                   │
Recovery Module (adopted from Self-Healing Orchestrators)  │
        │                                                   │
        ▼                                                   │
Level-2 Memory Layer (pgvector semantic feedback store)    │
        │                                                   │
        ▼                                                   │
PostgreSQL  ◄──────────────────────────────────────────────┘
```

---

## Project Structure

```
ABOS/
├── backend/                        # Python backend (FastAPI + LangGraph)
│   ├── main.py                     # FastAPI app entry point
│   ├── core/                       # Config, logging, security, dependencies
│   │   ├── config.py               # All settings (reads from .env)
│   │   ├── security.py             # JWT + password hashing
│   │   ├── dependencies.py         # FastAPI dependency injection
│   │   ├── logging.py              # Logging setup
│   │   └── exceptions.py           # Custom exceptions + handlers
│   ├── api/
│   │   └── v1/
│   │       ├── router.py           # Mounts all sub-routers
│   │       └── routes/             # One file per resource
│   │           ├── auth.py         # Register / Login / Refresh
│   │           ├── goals.py        # Submit and retrieve goals
│   │           ├── workflows.py    # View generated workflows
│   │           ├── executions.py   # Track agent executions
│   │           ├── agents.py       # Agent performance profiles
│   │           ├── metrics.py      # Evaluation metrics
│   │           └── feedback.py     # Level-2 memory feedback
│   ├── schemas/                    # Pydantic request/response models
│   ├── services/                   # Business logic layer
│   ├── db/
│   │   ├── session.py              # Async SQLAlchemy engine + session
│   │   ├── models/                 # ORM models (one per table)
│   │   └── migrations/             # Alembic migration files
│   ├── agents/                     # LangGraph agent system (core research)
│   │   ├── state.py                # ABOSState — shared graph state
│   │   ├── graph.py                # LangGraph graph definition
│   │   ├── planner/                # Goal-to-workflow planner node
│   │   ├── scheduler/              # Performance-based routing scheduler
│   │   ├── department/             # Department agents
│   │   │   ├── sales.py
│   │   │   ├── support.py
│   │   │   └── research.py
│   │   ├── memory/                 # Level-2 feedback memory layer
│   │   └── recovery/               # Failure recovery module (cited)
│   └── workers/                    # Celery tasks
│       ├── celery_app.py
│       └── tasks.py
├── frontend/                       # React + Vite + Tailwind dashboard
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── api/                    # API client (Axios)
│   │   └── store/                  # Zustand state management
│   └── ...
├── tests/                          # Pytest test suite
│   ├── unit/
│   ├── integration/
│   └── evaluation/                 # Research evaluation scripts
├── evaluation/                     # Experimental analysis (Pandas/NumPy/SciPy)
├── docker/                         # Dockerfiles
├── docker-compose.yml              # Local full-stack
├── docker-compose.cloud.yml        # Cloud overrides
├── pyproject.toml                  # Python dependencies (Poetry)
├── alembic.ini                     # Alembic config
└── .env.example                    # Environment variable template
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Primary language | Python 3.12+ | AI, agents, scheduler, evaluation |
| Agent orchestration | LangGraph | Stateful multi-agent workflow execution |
| LLM | Gemini API / OpenAI API | Goal understanding, decomposition, reasoning |
| LLM abstraction | LiteLLM | Switch providers without rewriting agents |
| Backend API | FastAPI | REST API |
| Workflow schema | Pydantic | Typed workflow representation |
| Database | PostgreSQL | Users, goals, workflows, executions, metrics |
| Vector memory | pgvector | Semantic retrieval of feedback |
| Task queue | Redis | Async execution state |
| Background workers | Celery | Long-running agent tasks |
| Frontend | React + Vite | ABOS dashboard |
| UI | Tailwind CSS | Styling |
| Visualization | Recharts | Performance and routing metrics |
| Authentication | JWT + OAuth2 | User auth |
| Containerization | Docker + Docker Compose | Reproducible local + cloud deployment |
| Testing | Pytest | Unit/integration tests |
| Evaluation | Pandas + NumPy + SciPy | Experimental analysis |
| Experiment tracking | MLflow | Metrics, configs, and run comparison |

---

## Getting Started (Local)

### Prerequisites

Make sure you have these installed:

- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation)
- Node.js 20+ and npm
- Docker Desktop (for PostgreSQL + Redis, or run them natively)
- Git

### 1. Clone the repo

```bash
git clone https://github.com/your-org/abos.git
cd abos
```

### 2. Set up environment variables

```bash
cp .env.example .env
# Edit .env and fill in your API keys and DB credentials
```

### 3. Install Python dependencies

```bash
poetry install
```

### 4. Start PostgreSQL and Redis via Docker

```bash
docker-compose up -d postgres redis
```

Or if you have them installed natively, make sure they are running and match the URLs in your `.env`.

### 5. Run database migrations

```bash
poetry run alembic upgrade head
```

### 6. Start the backend

```bash
poetry run uvicorn backend.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/api/docs

### 7. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at: http://localhost:5173

### 8. Start the Celery worker (separate terminal)

```bash
poetry run celery -A backend.workers.celery_app worker --loglevel=info
```

---

## Environment Variables

All config lives in `.env`. Copy `.env.example` and fill in values. Key variables:

| Variable | Description |
|---|---|
| `ACTIVE_LLM` | Which LLM to use, e.g. `gemini/gemini-1.5-pro` or `openai/gpt-4o` |
| `GEMINI_API_KEY` | Your Gemini API key |
| `OPENAI_API_KEY` | Your OpenAI API key |
| `DATABASE_URL` | PostgreSQL async connection string |
| `REDIS_URL` | Redis connection string |
| `JWT_SECRET_KEY` | Secret for signing JWTs — use a long random string in production |

**Never commit `.env` to git.** It is in `.gitignore`.

---

## Running the Backend

```bash
# Development (auto-reload)
poetry run uvicorn backend.main:app --reload --port 8000

# Production (inside Docker)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Interactive API docs: http://localhost:8000/api/docs

---

## Running the Frontend

```bash
cd frontend
npm install       # first time only
npm run dev       # development server on port 5173
npm run build     # production build
npm run preview   # preview the production build locally
```

---

## Database & Migrations

ABOS uses **Alembic** for schema migrations. Always use migrations — do not rely on `create_all` in production.

```bash
# Apply all pending migrations
poetry run alembic upgrade head

# Create a new migration after changing a model
poetry run alembic revision --autogenerate -m "describe your change"

# Roll back one migration
poetry run alembic downgrade -1

# View migration history
poetry run alembic history
```

**Important:** After changing any file in `backend/db/models/`, create a new migration and commit it.

---

## Agent System

The agent system lives in `backend/agents/`. This is the core research contribution.

### How it works

1. A goal is submitted via the API
2. Celery picks it up and invokes the LangGraph graph
3. The **Planner node** calls the LLM to decompose the goal into workflow steps
4. The **Scheduler** scores available agents per step using: `score = w1 * success_rate + w2 * (1 / latency) + w3 * confidence`
5. Each step is routed to the highest-scoring department agent
6. The **Recovery module** handles failures (adopted from Self-Healing Orchestrators, 2026)
7. Outcomes are written to the **Memory layer** (pgvector) for future retrieval

### Adding a new agent capability

1. Open the relevant agent file: `backend/agents/department/sales.py` (or support/research)
2. Add a new tool function decorated with `@tool`
3. Register it in the agent's tool list
4. No changes needed to the graph — the planner will use it automatically

### Changing the scheduler weights

Open `backend/agents/scheduler/scheduler.py` and adjust `WEIGHT_SUCCESS_RATE`, `WEIGHT_LATENCY`, `WEIGHT_CONFIDENCE`.

---

## Scheduler

The performance-based scheduler is in `backend/agents/scheduler/`.

It is a **heuristic, interpretable, non-RL scheduler** — this is a deliberate research design choice, not a limitation. It uses:

- `success_rate` — rolling window success rate over last N executions
- `avg_latency_ms` — rolling average latency (lower is better)
- `confidence_score` — composite score stored in `agent_profiles` table

This is explicitly positioned against MetaAgent-X's RL approach as a lightweight, deployable alternative. See the proposal for the full justification.

---

## Memory Layer

The memory layer is in `backend/agents/memory/`.

ABOS implements a **Level-2 explicit-feedback memory** layer per the Governance-by-Design (2026) maturity model:

- Feedback submitted via `POST /api/v1/feedback`
- Correction text is embedded via LiteLLM and stored as a 1536-dim vector in pgvector
- At planning time, semantically similar past feedback is retrieved and injected into the planner prompt
- Feedback also triggers an update to the agent's performance profile

---

## API Reference

Full interactive docs available at http://localhost:8000/api/docs when the backend is running.

Key endpoints:

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register a new user |
| POST | `/api/v1/auth/login` | Login and get tokens |
| POST | `/api/v1/goals/` | Submit a business goal |
| GET | `/api/v1/goals/` | List your goals |
| GET | `/api/v1/workflows/{id}` | Get a generated workflow |
| GET | `/api/v1/executions/` | List agent executions |
| POST | `/api/v1/feedback/` | Submit feedback (memory layer) |
| GET | `/api/v1/metrics/system` | System-level performance metrics |
| GET | `/api/v1/agents/` | Agent performance profiles |

---

## Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov=backend --cov-report=html

# Run only unit tests
poetry run pytest tests/unit/

# Run only integration tests (requires running DB + Redis)
poetry run pytest tests/integration/

# Run evaluation scripts
poetry run pytest tests/evaluation/
```

Test files live in `tests/`. Match the structure of `backend/` — e.g., `tests/unit/agents/test_scheduler.py` tests `backend/agents/scheduler/scheduler.py`.

---

## Experiment Tracking (MLflow)

ABOS uses MLflow to track evaluation runs, metrics, and configs.

```bash
# Start the MLflow tracking server (separate terminal)
poetry run mlflow ui --port 5000

# Dashboard available at:
# http://localhost:5000
```

Evaluation scripts in `evaluation/` log runs automatically. Each run records:
- Task completion rate
- Routing accuracy
- Recovery success rate
- Scheduler config (weights, window size)
- LLM used

---

## Docker (Local Full Stack)

Run the entire stack locally with one command:

```bash
# Start everything (PostgreSQL, Redis, backend, frontend, MLflow)
docker-compose up --build

# Start only infrastructure (DB + Redis), run backend/frontend natively
docker-compose up -d postgres redis

# Tear down
docker-compose down

# Tear down and delete volumes (wipes database)
docker-compose down -v
```

---

## Cloud Deployment

For cloud deployment (demo / shared access), use the cloud override file:

```bash
docker-compose -f docker-compose.yml -f docker-compose.cloud.yml up -d
```

Cloud-specific values (DB URL, Redis URL, API keys) are set via environment variables on the hosting platform — not via `.env` files. The codebase is identical.

Recommended platforms:
- **Railway** or **Render** — easiest for backend + PostgreSQL + Redis
- **Vercel** — frontend
- **Neon** — serverless PostgreSQL with pgvector support

---

## Team Responsibilities

| Area | Owner | Files |
|---|---|---|
| Goal Planner + LangGraph graph | | `backend/agents/planner/`, `backend/agents/graph.py` |
| Scheduler | | `backend/agents/scheduler/` |
| Department Agents | | `backend/agents/department/` |
| Memory Layer | | `backend/agents/memory/` |
| Backend API + DB | | `backend/api/`, `backend/db/`, `backend/services/` |
| Frontend Dashboard | | `frontend/` |
| Evaluation + MLflow | | `evaluation/`, `tests/evaluation/` |
| Docker + Deployment | | `docker/`, `docker-compose*.yml` |

> Fill in owner names above once responsibilities are assigned.

---

## Research Positioning

ABOS is explicitly positioned as:

- A **concrete instantiation** of the Agentic BPM Manifesto (2026) vision
- **Different from Autonoma** — ABOS takes business goals as input, not single-turn prompts; targets department coordination
- **Different from Agentic ERP** — ABOS focuses on adaptive goal-to-workflow generation; Agentic ERP uses a fixed 5-role orchestration
- **Different from MetaAgent-X** — ABOS uses a lightweight heuristic scheduler; MetaAgent-X requires RL training infrastructure

Failure recovery (Self-Healing Orchestrators, 2026) and memory maturity model (Governance by Design, 2026) are **adopted with citation — not claimed as novel contributions**.

The two novel contributions are:
1. Goal-driven adaptive workflow generation for business departments
2. Lightweight, interpretable performance-based scheduling (non-RL)

---

## Common Issues

**`asyncpg` connection refused**
Make sure PostgreSQL is running: `docker-compose up -d postgres`

**`alembic upgrade head` fails with "relation already exists"**
The DB was partially initialized. Run `alembic downgrade base` then `alembic upgrade head`.

**LLM calls failing**
Check `GEMINI_API_KEY` or `OPENAI_API_KEY` in your `.env`. Verify `ACTIVE_LLM` matches the provider.

**Celery worker not picking up tasks**
Make sure Redis is running and `CELERY_BROKER_URL` in `.env` is correct.

**pgvector extension missing**
Connect to your PostgreSQL DB and run: `CREATE EXTENSION IF NOT EXISTS vector;`
This is handled automatically in the Docker setup.

---

## Git Workflow

```bash
# Always work on a feature branch
git checkout -b feature/your-feature-name

# Commit often with clear messages
git commit -m "feat(agents): add confidence decay to scheduler scoring"

# Push and open a PR
git push -u origin feature/your-feature-name
```

Branch naming: `feature/`, `fix/`, `eval/`, `docs/`

Commit style: `type(scope): description`
Types: `feat`, `fix`, `refactor`, `test`, `docs`, `eval`, `chore`
