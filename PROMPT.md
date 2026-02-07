# DMARC Dashboard — Project Completion Loop

You are completing the DMARC Dashboard project. Your source of truth is `COMPLETION_PLAN.md` in this repo root. Each item is a checkbox. Your job: find unchecked items, implement them, verify them, check them off, commit, and move on.

## Environment Note

Docker uses the default socket: `export DOCKER_HOST=unix:///var/run/docker.sock`
Set this before running any docker/docker compose commands.

## STEP 1: Orient

Read `COMPLETION_PLAN.md`. Count total items vs checked items. Print:
```
Progress: X/Y items complete (Z%)
Current phase: Phase N — <name>
```

If ALL items are checked off (or marked as SKIPPED), output:
```
<promise>PROJECT COMPLETE</promise>
```
and stop.

## STEP 2: Check for Regressions

Before new work, run the test suite to make sure previous iterations didn't break anything:
```bash
docker compose exec backend pytest -x -q --tb=short 2>&1 | tail -20
cd e2e && npx playwright test --project=chromium --reporter=list 2>&1 | tail -30
```
If tests fail that passed before, fix regressions FIRST before proceeding.

## STEP 3: Select Next Items

Find the FIRST unchecked `- [ ]` items in phase priority order (Phase 1 before Phase 2, etc). Select 1-4 items from the SAME phase that can be worked on in parallel.

**Phase priority:** 1 > 2 > 3 > 4 > 5 > 6 > 7

**Skip rules:**
- If an item requires human decision (marked `NEEDS DECISION`), skip it
- If an item requires external infrastructure (K8s cluster, monitoring stack), skip it and mark: `- [x] SKIPPED — requires external infrastructure`
- If an item failed in 2 previous iterations (check git log), skip it and mark: `- [x] SKIPPED — blocked, see BLOCKED.md`

## STEP 4: Implement

Use an agent team. Spawn parallel agents for independent items. Each agent should:

1. Read the relevant source files before making changes
2. Follow existing code patterns (service layer, Pydantic schemas, FastAPI Depends)
3. Make minimal, focused changes — don't refactor surrounding code
4. Add tests for new/changed code when the item is in Phase 2, or when the change is non-trivial

**Key project patterns to follow:**
- Backend: Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2, service layer pattern
- Frontend: Vanilla JS (no frameworks), Chart.js, CSS custom properties for theming
- Tests: pytest (backend), Jest (frontend), Playwright (E2E)
- Docker: 7 services (backend, celery-worker, celery-beat, flower, db, redis, nginx)
- Auth: JWT (15-min access, 7-day refresh), stored in localStorage
- Config: `backend/app/config.py` uses env vars with defaults

**Important files:**
- `backend/app/main.py` — FastAPI entry point
- `backend/app/config.py` — Settings (60+ env vars)
- `backend/app/api/routes.py` — Core DMARC endpoints (largest file)
- `backend/app/api/` — 23 route modules
- `backend/app/models/` — SQLAlchemy models
- `backend/app/services/` — Business logic (35+ files)
- `frontend/js/app.js` — Monolithic frontend (~5000 lines)
- `frontend/css/styles.css` — Custom CSS (~6900 lines)
- `frontend/index.html` — Single-page app shell
- `docker-compose.yml` — Service definitions

## STEP 5: Verify

After implementation, run verification appropriate to the phase:

| Phase | Verification Command |
|-------|---------------------|
| Phase 1 (Security) | `docker compose config`, `grep -r "hardcoded\|password\|secret" docker-compose.yml` |
| Phase 2 (Tests) | `docker compose exec backend pytest -v --cov=app --tb=short` |
| Phase 3 (Features) | `docker compose exec backend pytest -v --tb=short` + E2E if UI changed |
| Phase 4 (Quality) | `docker compose exec backend pytest -v --tb=short`, `grep -rn "except:" backend/app/` |
| Phase 5 (Frontend) | `cd e2e && npx playwright test --project=chromium --reporter=list` |
| Phase 6 (Infra) | `docker compose config --quiet`, file existence checks |
| Phase 7 (Docs) | File existence and content checks |

If verification fails, fix the issue before proceeding. If you cannot fix it after 2 attempts, mark the item as SKIPPED in COMPLETION_PLAN.md and note the reason in `BLOCKED.md` (create if needed).

## STEP 6: Record & Commit

1. Update `COMPLETION_PLAN.md` — change `- [ ]` to `- [x]` for completed items
2. Stage changed files (be specific, don't `git add -A`)
3. Commit with message format:
   ```
   Complete Phase N.M: <brief description>

   - Item 1 description
   - Item 2 description (if multiple)

   Progress: X/Y items (Z%)
   ```
4. After committing, rebuild Docker if backend files changed:
   ```bash
   docker compose up -d --build backend celery-worker
   ```

## RULES

1. **One phase at a time.** Don't skip ahead to easier phases.
2. **Read before writing.** Always read source files before editing.
3. **Minimal changes.** Don't refactor, add comments, or "improve" code beyond the checklist item.
4. **Test everything.** Run tests after changes. Fix what you break.
5. **Commit often.** Commit after every 1-4 completed items, not at the end.
6. **Don't loop forever.** If stuck on an item, skip after 2 attempts.
7. **Restart services.** After backend changes: `docker compose up -d --build backend celery-worker`
8. **No secrets in commits.** Never commit real passwords, API keys, or tokens.
9. **Use .env pattern.** Replace hardcoded values with `os.getenv()` / `.env` file references.
10. **Respect existing architecture.** Don't introduce new frameworks, ORMs, or paradigms.
