# ABOS — Project Completion Roadmap

> **Last updated:** August 2026 — Kanika Kapoor
> **Thesis deadline:** April / May 2027 (4–5 months)
> **Current completion:** ~85%

---

## 1. Executive Summary

| Item | Detail |
|------|--------|
| Project | Adaptive Business Operating System (ABOS) |
| Type | B.Tech Major Project + Research Paper |
| Team | Kanika Kapoor · Ashmit Bhandari · Kaushal Thakur · Harshit Gahlot |
| Thesis timeline | 4–5 months (Jan – May 2027) |
| Critical blocker | LLM API errors preventing evaluation runs |
| Next action | Fix Gemini / switch to OpenAI → run evaluation |

### What is done
- Core agent system — 6 agents, 15 tools, LangGraph 6-node orchestration
- 3-tier performance-based scheduler with cold-start prior (0.41)
- Database schema with Alembic migrations
- Full FastAPI REST API (7 route files)
- Celery + Redis async worker setup
- Docker (local + cloud compose files)
- Evaluation framework structure (9 scenarios × 7 trials design)
- Unit tests — 15/15 passing
- All core documentation (SOURCE_OF_TRUTH, BASELINE_SPEC, AGENT_SYSTEM, TEAM_STATUS)
- Frontend scaffold — API client, UI components, Zustand stores

### What is remaining
- Fix LLM API → run 63 paired evaluation trials ← **BLOCKING**
- Statistical analysis + 5 publication figures
- Research paper (10–12 pages, IEEE format)
- Frontend pages (5 pages: Login, Dashboard, Goals, Workflow, Agents)
- Cloud deployment (Railway + Vercel)
- Full thesis document (60–80 pages)
- Presentation deck (15–20 slides)

---

## 2. Current Blocker — LLM API Fix

**Error:** `litellm.NotFoundError: GeminiException — models/gemini-1.5-flash is not found for API version v1beta`

### Option A — Switch to OpenAI (recommended, fastest)
```
1. Get API key: https://platform.openai.com/api-keys
2. Edit .env:
   ACTIVE_LLM=openai/gpt-4o-mini
   OPENAI_API_KEY=sk-...your-key...
3. Run smoke test (see Section 3)
```

### Option B — Fix Gemini configuration
```
1. Edit backend/agents/memory/embeddings.py line 17:
   "gemini": "gemini/models/text-embedding-004"
2. Edit .env:
   ACTIVE_LLM=gemini/gemini-1.5-flash-001
   GEMINI_API_VERSION=v1
3. Run smoke test (see Section 3)
```

### Smoke test command
```bash
cd "e:\Major Project\ABOS"
set PYTHONPATH=e:\Major Project\ABOS
.venv\Scripts\python.exe evaluation\run_evaluation.py --mode cold --scenario S1 --trials 1
```
**Expected:** completes in 3–5 minutes, prints a results table with no errors.

---

## 3. Month-by-Month Timeline

### Month 1 — January 2027: Evaluation & Results

| Week | Task | Deliverable |
|------|------|-------------|
| 1 | Fix LLM API, run smoke test | 1 trial completes cleanly |
| 2 | Run full evaluation (all 9 scenarios × 7 trials) | 63 paired trials logged to MLflow |
| 3 | Statistical analysis + visualizations | 5 publication-ready figures |
| 4 | Write evaluation results document | `docs/EVALUATION_RESULTS.md` |

**Full evaluation command:**
```bash
set PYTHONPATH=e:\Major Project\ABOS
.venv\Scripts\python.exe evaluation\run_evaluation.py --mode cold --scenario all --trials 7
```
Runtime: 4–6 hours. Generates comparison tables for TCR, RA, RSR, latency.

**5 figures to produce:**
1. Task Completion Rate — ABOS vs Baseline by scenario (bar chart)
2. Routing Accuracy comparison (grouped bar chart)
3. Average step latency (box plots per scenario)
4. Scheduler score vs step success correlation (scatter plot)
5. Recovery success rate across departments (stacked bar)

**Statistical validation:**
- Wilcoxon signed-rank test per scenario (n = 7 paired samples)
- Effect size: rank-biserial correlation
- Report: mean ± std, p-value, significance flag

---

### Month 2 — February 2027: Implementation Completion

| Week | Task | Deliverable |
|------|------|-------------|
| 1–2 | Complete frontend MVP (5 pages) | Working React dashboard |
| 3 | Cloud deployment | Live public URL |
| 4 | Demo video + screenshots | 3–5 min MP4, uploaded unlisted |

**Frontend pages still needed:**
```
frontend/src/pages/
├── LoginPage.tsx       — register / login form, JWT storage
├── DashboardPage.tsx   — goal submission form, recent goals list
├── GoalsPage.tsx       — goals table with status badges
├── WorkflowDetailPage.tsx — step-by-step workflow view, agent assignments
└── AgentsPage.tsx      — agent performance cards (TCR, latency, confidence)
```

**Frontend files already built:**
- `src/api/` — client.ts, auth.ts, goals.ts, workflows.ts, agents.ts, types.ts
- `src/components/` — Navbar, Sidebar, Badge, Button, Card, Input, Spinner
- `src/store/` — authStore.ts, uiStore.ts
- Still needed: `src/main.tsx`, `src/App.tsx`, `src/index.css`, all 5 page files

**Cloud deployment stack:**
| Service | Platform | Cost |
|---------|----------|------|
| Backend + workers | Railway | Free tier |
| PostgreSQL + pgvector | Neon | Free tier |
| Redis | Upstash | Free tier |
| Frontend | Vercel | Free tier |

---

### Month 3 — March 2027: Research Paper

| Week | Task | Deliverable |
|------|------|-------------|
| 1 | Complete first draft | Full 10–12 page paper |
| 2 | Advisor review round 1 | Marked-up draft |
| 3 | Revisions + review round 2 | Revised draft |
| 4 | Final polish, LaTeX formatting | Submission-ready paper |

**Paper structure (IEEE format, 10–12 pages):**
```
I.    Abstract (200–250 words)
II.   Introduction — motivation, gap, contributions (2 pages)
III.  Related Work — Autonoma, Agentic ERP, MetaAgent-X,
                     Self-Healing Orchestrators, Governance by Design (2–3 pages)
IV.   System Design — architecture, planner, scheduler, agents,
                       recovery, memory (3–4 pages)
V.    Evaluation — protocol, baseline, results, discussion (4–5 pages)
VI.   Limitations (0.5 page)
VII.  Conclusion & Future Work (0.5 page)
VIII. References (15–20 papers)
```

**Must cite, never claim as novel:**
- Self-Healing Agentic Orchestrators (2026) — arxiv 2606.01416 — recovery module
- Governance by Design (2026) — arxiv 2605.20210 — Level-2 memory model
- Autonoma (2026) — baseline comparison point
- APM Manifesto (2026) — conceptual foundation

**Two novel contributions (claim these):**
1. Goal-to-Workflow Planner — no prior system takes a business goal and generates a structured multi-department execution plan
2. Interpretable Performance-Based Scheduler — lightweight non-RL alternative for business-department agent routing

---

### Month 4 — April 2027: Thesis Document

| Week | Task | Deliverable |
|------|------|-------------|
| 1–2 | Expand paper into full thesis | Full chapter drafts |
| 3 | Formatting, appendices, references | Complete document |
| 4 | Review + corrections | Advisor-approved thesis |

**Thesis structure (60–80 pages):**
```
Cover Page · Certificate · Acknowledgments · Abstract (500 words)
Table of Contents · List of Figures · List of Tables · Abbreviations

Chapter 1: Introduction
Chapter 2: Literature Review
Chapter 3: System Design
Chapter 4: Implementation
Chapter 5: Evaluation
Chapter 6: Results & Discussion
Chapter 7: Conclusion & Future Work

References
Appendix A: Code Repository Structure
Appendix B: API Endpoint Documentation
Appendix C: Raw Evaluation Data Tables
Appendix D: User Manual
```

**Formatting requirements:**
- Font: Times New Roman 12pt, 1.5 line spacing
- Margins: 1.25" left, 1" right, 0.75" top/bottom
- Reference style: IEEE

---

### Month 5 — May 2027: Defense Preparation & Submission

| Week | Task | Deliverable |
|------|------|-------------|
| 1 | Presentation deck | 15–20 slides |
| 2 | Dry runs (3–5 practice sessions) | Confident delivery |
| 3 | Final thesis submission | Submitted |
| 4 | Thesis defense | Passed |

**Presentation structure (15 min talk + 5 min Q&A):**
```
Slide 1:   Title + team
Slides 2–3: Motivation & problem
Slide 4:   Contributions
Slides 5–6: System architecture
Slides 7–8: Planner design
Slides 9–11: Scheduler design + evidence hierarchy
Slides 12–14: Evaluation design + results
Slides 15–16: Demo screenshots
Slides 17–18: Key findings
Slide 19:  Limitations & future work
Slide 20:  Conclusion + Q&A
```

---

## 4. Target Users & Business Viability

### Who Uses ABOS

**Primary users — the people who submit goals:**

| User | Role | Example Goal |
|------|------|-------------|
| Business Operations Manager | Oversees Sales + Support + Research | "Run Q4 outreach for dormant enterprise leads" |
| Sales Director | Manages outreach and pipeline | "Identify 20 at-risk deals and draft follow-ups" |
| Support Team Lead | Handles ticket backlog | "Triage 50 open tickets, draft responses for top 10" |
| Business Analyst | Produces reports | "Generate monthly KPI summary for last 30 days" |

**Target organizations:**
- SMEs with 50–500 employees
- Annual revenue $5M–$50M
- Have Sales, Support, and Research/Analytics functions
- Currently using manual or rule-based automation (Zapier, Make.com)

### Market Sizing

| Market | Size | Notes |
|--------|------|-------|
| TAM — operations automation | $15B+ | Global market |
| SAM — SME business operations | $2B | 50–500 employee companies |
| SOM — adaptive multi-dept automation | $200M | Addressable in 3–5 years |

### Competitive Differentiation

| Competitor | Their approach | ABOS difference |
|-----------|---------------|-----------------|
| Zapier / Make.com | Rule-based triggers | ABOS uses natural language goals + AI routing |
| Salesforce Flow | CRM-only, expensive | ABOS is cross-department, lightweight |
| ServiceNow | Enterprise IT focus | ABOS targets SME business operations |
| MetaAgent-X | RL-based scheduler | ABOS uses interpretable heuristic, no training needed |

### Revenue Model (post-thesis, optional)

| Tier | Price | Limits |
|------|-------|--------|
| Starter | $99/month | 100 goals/month, 3 departments |
| Professional | $299/month | Unlimited goals, custom agents |
| Enterprise | Custom | On-premise, SLA, dedicated support |

---

## 5. Risk Register

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| LLM API keeps failing | Critical | Medium | Switch to OpenAI immediately — $5 credit is enough for all trials |
| Evaluation shows no improvement over baseline | High | Low | Negative result is still valid — document and explain in paper |
| Advisor delays feedback | High | Medium | Submit drafts 1 week early, build in buffer per review cycle |
| Frontend takes longer than expected | Medium | High | Descope to 3 pages (Login, Dashboard, Goals) — Workflow + Agents are nice-to-have |
| Cloud costs exceed free tier | Medium | Low | All services have generous free tiers sufficient for demo |
| Thesis formatting issues | Low | Medium | Use university LaTeX template from day 1, not Word |

---

## 6. Documentation Update Checklist

### Needed immediately (after evaluation runs)
- [ ] Create `docs/EVALUATION_RESULTS.md` — tables, figures, statistical interpretation
- [ ] Update `docs/SOURCE_OF_TRUTH.md` Section 13 — mark Phase 2 tasks complete
- [ ] Update `README.md` — add Evaluation Results section, link to demo

### Needed before thesis submission
- [ ] Create `docs/USER_MANUAL.md` — register, login, submit goal, view results
- [ ] Create `docs/THESIS_APPENDIX.md` — repo structure, API docs, raw data tables
- [ ] Update `docs/DEPLOYMENT_GUIDE.md` — production environment variables, cloud URLs

### Optional (for productization)
- [ ] Create `docs/MARKET_ANALYSIS.md` — ICP, competitive landscape, revenue model
- [ ] Create `docs/USER_FEEDBACK.md` — pilot user interview findings

---

## 7. Success Criteria

### Minimum for thesis approval
- [ ] Evaluation complete — 63 paired trials (9 scenarios × 7 trials)
- [ ] Statistical validation — Wilcoxon p-values, effect sizes reported
- [ ] Research paper written — 10–12 pages, IEEE format, advisor-approved
- [ ] Thesis document complete — 60–80 pages, all chapters
- [ ] Presentation prepared — 15–20 slides, rehearsed

### For a strong grade
- [ ] Working web dashboard deployed to public URL
- [ ] Demo video (3–5 minutes) showing end-to-end workflow
- [ ] All unit tests passing
- [ ] Clean, well-documented codebase

### For future productization (optional)
- [ ] 5–10 pilot users onboarded
- [ ] User feedback report written
- [ ] Go-to-market strategy documented

---

## 8. Immediate Next Actions (This Week)

```
Day 1–2:  Fix LLM API (Option A or B above)
Day 3:    Run smoke test — 1 trial of S1
Day 4–5:  Run full evaluation — all 9 scenarios × 7 trials (4–6 hrs)
Week 2:   Statistical analysis + 5 figures
Week 2:   Write docs/EVALUATION_RESULTS.md
```

> **The evaluation is the thesis.** Everything else — frontend, deployment, business analysis — is secondary until evaluation results exist.

---

*Last updated: August 2026*
