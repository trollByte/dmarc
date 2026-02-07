# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records documenting key technical decisions made in the DMARC Dashboard project.

## What are ADRs?

Architecture Decision Records (ADRs) capture important architectural decisions along with their context and consequences. They serve as historical documentation to help current and future team members understand:

- Why a particular technology or approach was chosen
- What alternatives were considered
- What trade-offs were accepted
- When the decision should be reconsidered

## ADR Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [001](001-vanilla-js-frontend.md) | Vanilla JavaScript Frontend (No React/Vue/Angular) | Accepted | 2026-01-15 |
| [002](002-holt-winters-forecasting.md) | Holt-Winters Exponential Smoothing (Not LSTM) | Accepted | 2026-01-20 |
| [003](003-celery-with-apscheduler-fallback.md) | Celery with APScheduler Fallback | Accepted | 2026-01-10 |

## ADR Format

Each ADR follows this structure:

```markdown
# ADR XXX: Title

**Status:** Accepted | Rejected | Deprecated | Superseded

**Date:** YYYY-MM-DD

**Context:**
What is the issue we're trying to solve?

**Decision:**
What did we decide to do?

**Rationale:**
Why did we make this decision?

**Trade-offs and Limitations:**
What are we giving up?

**When to Reconsider:**
Under what conditions should we revisit this decision?

**Alternatives Rejected:**
What other options did we consider and why were they rejected?

**Conclusion:**
Summary and final thoughts
```

## Key Decisions Documented

### 001: Vanilla JavaScript Frontend

**Why it matters:** Choosing no framework impacts development speed, maintenance, and hiring.

**Key insight:** For a dashboard of low-medium complexity with a backend-focused team, vanilla JavaScript provides simplicity and performance without framework overhead.

### 002: Holt-Winters Forecasting

**Why it matters:** Forecasting approach determines dependency size, training time, and operational complexity.

**Key insight:** Classical time-series methods (Holt-Winters) are sufficient for email volume forecasting, avoiding the complexity and dependencies of deep learning (LSTM/TensorFlow).

### 003: Celery with APScheduler Fallback

**Why it matters:** Task processing architecture determines scalability and deployment complexity.

**Key insight:** Hybrid approach allows production scale with Celery while maintaining development simplicity with APScheduler.

## How to Use ADRs

### As a Developer

**Before making a major change:**
1. Check if an ADR exists for that area
2. Understand the original context and rationale
3. Determine if the decision still applies

**When proposing a new approach:**
1. Create a new ADR documenting your proposal
2. Include context, alternatives, and trade-offs
3. Share with team for review

### As a New Team Member

**Start here to understand:**
- Why vanilla JavaScript instead of React?
- Why Holt-Winters instead of LSTM?
- Why both Celery and APScheduler?
- What trade-offs were accepted?

### When to Create a New ADR

Create an ADR when making decisions about:
- Technology stack changes (frameworks, databases, languages)
- Architectural patterns (microservices vs monolith, event-driven)
- Infrastructure choices (cloud provider, deployment approach)
- Security approaches (authentication, encryption)
- Data storage strategies (SQL vs NoSQL, caching)

**Don't create ADRs for:**
- Minor implementation details
- Bug fixes
- Code style preferences
- Temporary workarounds

## ADR Lifecycle

**Statuses:**
- **Proposed:** Under discussion, not yet decided
- **Accepted:** Decision made and being implemented
- **Deprecated:** No longer recommended, but still in use
- **Superseded:** Replaced by a newer ADR
- **Rejected:** Considered but not adopted

**When to update an ADR:**
- Mark as **Deprecated** when the decision is no longer recommended
- Mark as **Superseded** and reference the new ADR when replaced
- Add "Lessons Learned" section after significant time has passed

## Further Reading

- [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) by Michael Nygard
- [ADR GitHub Organization](https://adr.github.io/)
- [Architecture Decision Records: A Primer](https://www.thoughtworks.com/radar/techniques/lightweight-architecture-decision-records)

## Contributing

When creating a new ADR:

1. Use the next sequential number (004, 005, etc.)
2. Follow the standard format above
3. Be specific: Include code examples, benchmarks, and concrete trade-offs
4. Update this README with the new ADR in the index
5. Get review from at least one team member before merging
