# ABOS — Team Status & Handoff Document

> Last updated: August 16, 2026
> Maintained by: Kanika Kapoor
> Update this file every time something significant is completed or changed.

---

## Project in One Line

ABOS takes a high-level business goal (e.g. *"Run a Q4 outreach campaign for cold enterprise leads"*) and automatically breaks it into a multi-step workflow, routes each step to the right department agent (Sales / Support / Research), executes it, and learns from feedback to improve future routing.

---

## Repository

| Item | Value |
|---|---|
| GitHub | https://github.com/kanikakapoorcode/ABOS-Major |
| Default branch | `kanika-branch` (set this as default in GitHub Settings) |
| Stable branch | `main` — setup files only, do NOT push code here directly |
| Your work goes on | `feature/your-feature-name` branched off `kanika-branch` |

### How to get started

```bash
git clone https://github.com/kanikakapoorcode/ABOS-Major.git
cd ABOS-Major
git checkout kanika-branch
git checkout -b feature/your-task-name
```

---

## Current State — What's Built

### ✅ Project Config
- `.gitignore` — excludes `.env`, `node_modules`, `__pycache__`, `mlruns`, etc.
- `.env.example` — copy this to `.env` and fill in your API keys
- `pyproject.toml` — all Python dependencies (managed by Poetry)
- `alembic.ini` — database migration config
- `README.md` — full project overview and all commands

### ✅ Backend — FastAPI (`backend/`)

```
backend/
├── main.py                  ← FastAPI app, CORS, middleware, startup
├── core/
│   ├── config.py            ← All settings from .env (typed, validated)
│   ├── security.py          ← JWT creation/verification, password hashing
│   ├── dependencies.py      ← get_db(), get_current_user_id() for route injection
│   ├── logging.py           ← Logging setup
│   └── exceptions.py        ← Custom exceptions + global error handlers
├── api/v1/routes/
│   ├── auth.py              ← POST /register, /login, /refresh
│   ├── goals.py             ← POST/GET/DELETE /goals
│   ├── workflows.py         ← GET /workflows, POST /workflows/{id}/retry
│   ├── executions.py        ← GET /executions
│   ├── agents.py            ← GET /agents (performance profiles)
│   ├── metrics.py           ← GET /metrics/system, /agents, /routing
│   └── feedback.py          ← POST/GET /feedback (Level-2 memory write path)
├── schemas/                 ← Pydantic request/response models (typed I/O)
└── services/                ← Business logic (goal, workflow, execution, feedback, metrics)
```

**Status:** Fully scaffolded. Routes, schemas, and services are wired up.
DB calls use stubs/selects — real data flows once the DB is running.

### ✅ Database — PostgreSQL + pgvector (`backend/db/`)

```
Tables created:
  users             ← accounts
  goals             ← submitted business goals
  workflows         ← generated multi-step plans
  workflow_steps    ← individual steps within a workflow
  executions        ← agent execution records (one per step attempt)
  agent_profiles    ← performance metrics per agent (used by scheduler)
  feedback          ← Level-2 memory: corrections + 1536-dim pgvector embedding
```

**Alembic is configured** but the first migration file hasn't been generated yet.
Run this once the DB is up:
```bash
poetry run alembic revision --autogenerate -m "initial schema"
poetry run alembic upgrade head
```

### ✅ Agent System — LangGraph (`backend/agents/`)

This is the core research contribution. Read `docs/AGENT_SYSTEM.md` for full details.

```
agents/
├── state.py          ← ABOSState — the typed dict passed between every graph node
├── graph.py          ← LangGraph graph: nodes + conditional routing edges
├── executor.py       ← executor_node (runs steps) + summarizer_node
├── planner/
│   ├── planner.py    ← Goal-to-workflow decomposition (LLM call via LiteLLM)
│   └── prompts.py    ← Prompt templates — iterate here to improve output quality
├── scheduler/
│   ├── scheduler.py  ← Routes steps to best agent per department
│   └── scoring.py    ← Score = 0.5*success_rate + 0.2*latency_score + 0.3*confidence
├── department/
│   ├── base.py       ← BaseDepartmentAgent (all agents inherit this)
│   ├── sales.py      ← Sales agent + 5 tools (search_leads, draft_outreach, etc.)
│   ├── support.py    ← Support agent + 5 tools (triage_ticket, draft_response, etc.)
│   └── research.py   ← Research agent + 5 tools (query_data, analyze_trends, etc.)
├── memory/
│   ├── memory.py     ← Level-2 memory: pgvector retrieval + embedding storage
│   └── embeddings.py ← LiteLLM embedding calls
└── recovery/
    ├── classifier.py ← Classify failure type (timeout/llm_error/tool_error/etc.)
    └── recovery.py   ← Recovery node: retry / reroute / skip based on failure type
```

**Graph flow:**
```
START → memory_retrieval → planner → scheduler → executor
                                                     ↓ success → next step or summarizer
                                                     ↓ failure → recovery → retry or skip
                                              summarizer → END
```

**Important:** Tool implementations in `sales.py`, `support.py`, `research.py` are stubs.
They return placeholder strings. This is intentional — real integrations come later.

### ✅ Background Workers — Celery + Redis (`backend/workers/`)

```
celery_app.py   ← Celery config, 4 named queues
tasks.py        ← 4 tasks:
  execute_goal_task          ← triggered when a goal is submitted
  execute_workflow_task      ← triggered on workflow retry
  update_agent_profile_task  ← triggered after feedback submitted
  store_feedback_embedding_task ← embeds feedback correction for pgvector
```

### ✅ Frontend Config (`frontend/`)

Base config files created. Source code (`src/`) not yet written.

```
frontend/
├── package.json      ← All dependencies: React 18, Vite, Tailwind, Recharts,
│                       Zustand, React Query, React Hook Form, Zod, Axios
├── vite.config.ts    ← Dev server on :5173, proxies /api → backend :8000
├── tsconfig.json     ← TypeScript strict mode
├── tailwind.config.js ← Brand colors, Inter font
├── postcss.config.js
└── index.html        ← Root HTML shell
```

`src/` is empty — this is the main frontend task remaining.

### ✅ Documentation (`docs/`)

| File | Contents |
|---|---|
| `docs/SETUP.md` | Step-by-step local setup guide |
| `docs/AGENT_SYSTEM.md` | Full agent system deep dive |
| `docs/EVALUATION.md` | Research evaluation protocol + metrics |
| `docs/GIT_WORKFLOW.md` | Branch strategy, commit format, PR rules |
| `docs/TEAM_STATUS.md` | This file |

---

## What's Left to Build

### 🔲 Priority 1 — Docker (blocks everyone)

Nobody can run the full stack locally without this. Needed files:

```
docker/Dockerfile.backend       ← Python 3.12 + uvicorn
docker/Dockerfile.frontend      ← Node build + nginx serve
docker-compose.yml              ← postgres+pgvector, redis, backend, celery, frontend, mlflow
docker-compose.cloud.yml        ← Cloud overrides (swap local ports/volumes for cloud URLs)
```

### 🔲 Priority 2 — Frontend `src/`

The full React dashboard. Suggested structure:

```
frontend/src/
├── main.tsx                    ← React entry point
├── App.tsx                     ← Router (React Router v6)
├── api/
│   ├── client.ts               ← Axios instance with JWT interceptor
│   ├── goals.ts                ← goal API calls
│   ├── workflows.ts
│   ├── executions.ts
│   ├── metrics.ts
│   └── feedback.ts
├── store/
│   ├── authStore.ts            ← Zustand: token, user, login/logout
│   └── uiStore.ts              ← sidebar open/close, notifications
├── pages/
│   ├── LoginPage.tsx
│   ├── DashboardPage.tsx       ← Overview: recent goals, system metrics
│   ├── GoalsPage.tsx           ← Submit goal form + goal list
│   ├── WorkflowDetailPage.tsx  ← Steps, status, timeline
│   ├── MetricsPage.tsx         ← Recharts: completion rate, latency, routing accuracy
│   └── AgentsPage.tsx          ← Agent performance profiles table
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   └── Navbar.tsx
│   ├── ui/
│   │   ├── Badge.tsx           ← status badges (pending/running/completed/failed)
│   │   ├── Card.tsx
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   └── Spinner.tsx
│   └── charts/
│       ├── CompletionRateChart.tsx   ← LineChart (Recharts)
│       ├── LatencyChart.tsx          ← BarChart
│       ├── RoutingAccuracyChart.tsx  ← AreaChart
│       └── AgentScoreChart.tsx       ← RadarChart
└── hooks/
    ├── useGoals.ts
    ├── useWorkflow.ts
    └── useMetrics.ts
```

### 🔲 Priority 3 — First Alembic Migration

```bash
# Run once DB is up:
poetry run alembic revision --autogenerate -m "initial schema"
poetry run alembic upgrade head
```

Commit the generated file in `backend/db/migrations/versions/`.

### 🔲 Priority 4 — Tests (`tests/`)

```
tests/
├── conftest.py                          ← pytest fixtures: test DB, mock LLM
├── unit/
│   ├── agents/
│   │   ├── test_scheduler.py            ← scoring formula, edge cases
│   │   ├── test_planner.py              ← JSON parse, validation, fallbacks
│   │   └── test_classifier.py          ← failure classification rules
│   └── services/
│       └── test_goal_service.py
└── integration/
    ├── test_goals_api.py                ← submit goal → workflow created
    └── test_feedback_api.py             ← feedback → profile update
```

### 🔲 Priority 5 — Evaluation Scripts (`evaluation/`)

```
evaluation/
├── run_evaluation.py     ← Full ABOS vs baseline eval, logs to MLflow
├── baseline.py           ← Static-workflow baseline (fixed routing, no scheduler)
├── ablation.py           ← Run with components disabled (no scheduler, no memory, etc.)
├── compare.py            ← Statistical comparison (Wilcoxon test)
└── export_latex.py       ← Export results as LaTeX tables for the paper
```

### 🔲 Priority 6 — Debug Script

```
scripts/run_agent_debug.py   ← Invoke the graph directly without API/Celery
```

---

## Tech Stack Quick Reference

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Agent orchestration | LangGraph |
| LLM | Gemini API or OpenAI API via LiteLLM |
| Backend | FastAPI + Uvicorn |
| Database | PostgreSQL + pgvector |
| Task queue | Redis + Celery |
| Frontend | React 18 + Vite + TypeScript |
| Styling | Tailwind CSS |
| Charts | Recharts |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Migrations | Alembic |
| Testing | Pytest |
| Experiments | MLflow |
| Containers | Docker + Docker Compose |

---

## Key Files to Know

| If you want to... | Look at... |
|---|---|
| Understand the whole system | `README.md` |
| Set up locally | `docs/SETUP.md` |
| Understand the agent graph | `docs/AGENT_SYSTEM.md` |
| Change how goals are decomposed | `backend/agents/planner/prompts.py` |
| Change scheduler weights | `backend/agents/scheduler/scoring.py` |
| Add a tool to an agent | `backend/agents/department/sales.py` (or support/research) |
| Add an API endpoint | `backend/api/v1/routes/` + `backend/schemas/` + `backend/services/` |
| Add a DB table | `backend/db/models/` then run `alembic revision --autogenerate` |
| Run experiments | `evaluation/` |
| Check env variables | `.env.example` |

---

## Research Reminder — What's Novel vs Adopted

| Component | Status | Claim |
|---|---|---|
| Goal-to-workflow planner | **NOVEL** | No prior system does business-goal → multi-dept workflow |
| Performance-based scheduler | **NOVEL** | Lightweight non-RL alternative to MetaAgent-X |
| Level-2 memory layer | Adopted framework, our implementation | Cite Governance-by-Design (2026) |
| Failure recovery module | **Adopted — cite only** | Self-Healing Orchestrators (2026), arxiv 2606.01416 |
| Department-aligned agents | Architecture pattern | Differentiate from Agentic ERP's fixed orchestration |

> **Never claim failure recovery or the memory maturity model as novel contributions in any writeup, presentation, or viva.**

---

## Environment Setup Checklist (per person)

- [ ] Clone repo and switch to `kanika-branch`
- [ ] Copy `.env.example` → `.env` and fill in API keys
- [ ] Run `poetry install`
- [ ] Run `docker-compose up -d postgres redis`
- [ ] Run `poetry run alembic upgrade head`
- [ ] Run `poetry run uvicorn backend.main:app --reload`
- [ ] Run `poetry run celery -A backend.workers.celery_app worker --loglevel=info`
- [ ] Open http://localhost:8000/api/docs — API docs should load
- [ ] (Frontend) `cd frontend && npm install && npm run dev`
- [ ] Open http://localhost:5173

---

## Contact / Questions

Raise issues on GitHub or message the team directly.
For anything touching the agent system or scheduler — check with Kanika first before changing core logic.
