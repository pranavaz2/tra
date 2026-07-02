# docs/adr/ — Architecture Decision Records

This folder contains **Architecture Decision Records (ADRs)** for Travix AI.

An ADR documents a significant architectural decision: what was decided, the context that
drove the decision, the alternatives that were considered, and the consequences of the choice.

---

## Purpose

ADRs exist to answer the question: **"Why is the system designed this way?"**

Without ADRs, significant decisions live only in the heads of the people who made them. As
the team grows and time passes, this knowledge is lost. ADRs make architectural reasoning
permanent and searchable.

---

## ADR Status Values

| Status | Meaning |
|---|---|
| `Proposed` | Decision is under discussion — not yet final |
| `Accepted` | Decision is final and in effect |
| `Deprecated` | Decision was accepted but has since been superseded |
| `Superseded by ADR-XXX` | Replaced by a newer decision |

---

## File Naming Convention

```
ADR-{number}-{short-title}.md
```

Examples:
- `ADR-001-modular-monolith-over-microservices.md`
- `ADR-002-arq-for-async-task-queue.md`
- `ADR-003-ai-provider-abstraction-layer.md`
- `ADR-004-refresh-token-rotation-strategy.md`

Numbers are sequential and never reused. ADRs are **append-only** — never edit or delete
a superseded ADR. Mark it as `Deprecated` or `Superseded by ADR-XXX` and create a new one.

---

## ADR Template

```markdown
# ADR-{number} — {Title}

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXX
**Deciders:** {names or roles}

## Context

What is the situation or problem that requires a decision?
What forces are at play? What constraints exist?

## Decision

What was decided? State it clearly in one or two sentences.

## Alternatives Considered

| Alternative | Reason Rejected |
|---|---|
| Option A | ... |
| Option B | ... |

## Consequences

### Positive
- ...

### Negative / Trade-offs
- ...

## References
- Link to related ADRs, external docs, or prior art
```

---

## Existing ADRs

| ADR | Title | Status |
|---|---|---|
| [ADR-001](ADR-001-modular-monolith-over-microservices.md) | Modular Monolith Over Microservices | Accepted |
| [ADR-002](ADR-002-arq-over-celery-for-task-queue.md) | ARQ Over Celery for Async Task Queue | Accepted |
| [ADR-003](ADR-003-hs256-jwt-with-rs256-migration-path.md) | HS256 JWT with Planned RS256 Migration Path | Accepted |
