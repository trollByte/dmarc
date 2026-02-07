# DMARC Dashboard — Full Project Completion Design

## Approach: Ralph Loop + Agent Teams

### How It Works

Each ralph-loop iteration receives the same prompt. The prompt instructs Claude to:

1. **Orient** — Read `COMPLETION_PLAN.md`, count checked vs unchecked items
2. **Select** — Find the first unchecked `- [ ]` item in priority order (Phase 1 first)
3. **Plan** — Determine what code changes are needed for 1-4 items in the current phase
4. **Execute** — Spawn an agent team to implement items in parallel
5. **Verify** — Run relevant tests (pytest, jest, playwright, docker compose)
6. **Record** — Check off completed items with `- [x]`, commit to git
7. **Exit** — Ralph loop restarts with same prompt; next iteration picks up

### Agent Team Structure (Per Iteration)

Each iteration spawns up to 4 agents based on the current phase:

| Phase | Agent Roles | Verification |
|-------|-------------|--------------|
| Phase 1: Security | security-hardener, frontend-fixer | `docker compose up`, manual review |
| Phase 2: Tests | test-writer-1, test-writer-2, test-writer-3 | `pytest --cov`, `jest --coverage` |
| Phase 3: Features | feature-impl-1, feature-impl-2 | `pytest`, E2E tests |
| Phase 4: Quality | exception-fixer, error-handler | `pytest`, `grep -r "except:"` |
| Phase 5: Frontend | css-fixer, a11y-fixer | Playwright E2E, visual check |
| Phase 6: Infra | k8s-agent, ci-cd-agent, monitoring-agent | `kubectl dry-run`, `docker compose config` |
| Phase 7: Docs | doc-writer | File existence checks |

### Completion Criteria

The loop terminates when ALL items in COMPLETION_PLAN.md are checked:
```
<promise>PROJECT COMPLETE</promise>
```

### Estimated Iterations

- Phase 1 (13 items): ~4-5 iterations
- Phase 2 (20 items): ~8-10 iterations
- Phase 3 (8 items): ~4-5 iterations
- Phase 4 (9 items): ~2-3 iterations
- Phase 5 (11 items): ~3-4 iterations
- Phase 6 (14 items): ~5-6 iterations
- Phase 7 (7 items): ~2-3 iterations

**Total: ~28-36 iterations**

### Risks & Mitigations

1. **Iteration gets stuck on hard item** — Prompt includes instruction to skip after 2 failed attempts and create a `BLOCKED.md` note
2. **Tests break from previous iteration** — Each iteration starts by running existing tests; fixes regressions before new work
3. **Docker services need restart** — Prompt includes `docker compose restart` after backend changes
4. **Database migrations needed** — Prompt includes Alembic migration generation when models change
5. **Context window limits** — Agent teams keep individual agent context small; leader summarizes

### What Ralph Loop Cannot Do

These items require human judgment and are marked for skip:
- Phase 3.7: "Decide: drop LSTM from docs or implement" — needs product decision
- Phase 6.1: "Choose deployment target" — needs infrastructure decision
- Phase 6.2: Kubernetes changes — needs cluster access
- Phase 6.3: Grafana/Prometheus — needs running monitoring stack
