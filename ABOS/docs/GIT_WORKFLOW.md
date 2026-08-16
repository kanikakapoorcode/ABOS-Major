# ABOS — Git Workflow

---

## Branches

| Branch | Purpose |
|---|---|
| `main` | Stable, working code only. Never push directly. |
| `dev` | Integration branch. Merge feature branches here first. |
| `feature/your-feature` | Your work. Branch off `dev`. |
| `fix/bug-name` | Bug fixes. Branch off `dev`. |
| `eval/experiment-name` | Evaluation scripts and results. |
| `docs/topic` | Documentation updates. |

---

## Daily Workflow

```bash
# 1. Start your day — pull latest changes
git checkout dev
git pull origin dev

# 2. Create your feature branch
git checkout -b feature/scheduler-confidence-decay

# 3. Work, commit often
git add backend/agents/scheduler/scoring.py
git commit -m "feat(scheduler): add confidence decay for stale agents"

# 4. Push your branch
git push -u origin feature/scheduler-confidence-decay

# 5. Open a Pull Request to dev on GitHub
# Get at least one teammate to review before merging
```

---

## Commit Message Format

```
type(scope): short description

Optional longer explanation if needed.
```

**Types:**
- `feat` — new feature or capability
- `fix` — bug fix
- `refactor` — code restructure (no behaviour change)
- `test` — adding or updating tests
- `eval` — evaluation scripts or results
- `docs` — documentation
- `chore` — config, dependencies, build

**Scopes:** `agents`, `scheduler`, `planner`, `memory`, `recovery`, `api`, `db`, `frontend`, `docker`, `eval`

**Examples:**
```
feat(planner): add department-hint injection to decomposition prompt
fix(scheduler): handle division by zero when latency is 0
eval(baseline): add static routing baseline evaluation script
docs(agents): update memory layer description in AGENT_SYSTEM.md
```

---

## Pull Request Rules

1. PRs go to `dev`, not `main`
2. At least one teammate reviews before merge
3. All tests must pass
4. Write a clear PR description: what changed and why
5. Link to any relevant task or issue

---

## What NOT to Commit

- `.env` files (secrets)
- `__pycache__/` directories
- `node_modules/`
- `mlruns/` (MLflow local data)
- Large binary files or model weights
- Jupyter notebook outputs (clear outputs before committing)

These are all in `.gitignore` — but double-check before committing if you're unsure.

---

## Resolving Conflicts

```bash
# If dev has moved ahead while you were working:
git checkout dev
git pull origin dev
git checkout feature/your-feature
git rebase dev     # rebase your branch on top of latest dev

# Resolve any conflicts in your editor, then:
git add .
git rebase --continue
git push --force-with-lease origin feature/your-feature
```

Use `rebase` for cleaner history. Use `merge` only if rebase causes too many conflicts.
