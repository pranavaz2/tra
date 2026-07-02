# docs/decisions/ — Engineering Decisions

This folder captures **engineering decisions** that are significant enough to document but
do not meet the threshold for a full Architecture Decision Record (ADR).

---

## Purpose

Not every engineering decision warrants the formal ADR format. This folder captures decisions
that are:

- **Scoped to a single module or feature** (rather than system-wide)
- **Implementation choices** within an already-decided architectural direction
- **Tooling selections** that affect developer workflow but not system architecture
- **Coding conventions** established during development that aren't in CLAUDE.md

Think of this folder as the engineering team's decision log — a lightweight alternative to
ADRs for smaller choices that still deserve documentation.

---

## When to Use ADR vs. Decision

| Scenario | Where to Document |
|---|---|
| Choosing Modular Monolith over microservices | `docs/adr/` — system-wide |
| Choosing ARQ over Celery for task queue | `docs/adr/` — system-wide |
| Choosing a specific Pydantic validation pattern | `docs/decisions/` — implementation |
| Deciding how to structure trip-module error codes | `docs/decisions/` — module-scoped |
| Choosing an icon library for Flutter | `docs/decisions/` — tooling |

---

## File Naming Convention

```
{YYYY-MM-DD}-{short-title}.md
```

Examples:
- `2025-01-15-pydantic-error-serialization-pattern.md`
- `2025-02-01-flutter-icon-library-selection.md`
- `2025-02-10-trip-module-pagination-approach.md`

---

## Template

```markdown
# {Title}

**Date:** YYYY-MM-DD
**Author:** {name or role}
**Scope:** {module / feature / tooling}

## Decision

What was decided? (one paragraph maximum)

## Reason

Why was this decision made?

## Notes

Any caveats, follow-up tasks, or things to revisit.
```

---

## Status

> No decisions documented yet. This folder will grow as the project develops.
