# docs/tasks/ — Engineering Task Specifications

This folder contains **engineering task specifications** for Travix AI.

Each task that involves implementation work has a corresponding specification file here.
The specification is the **source of truth** for what needs to be built. Engineers and AI
agents must read the relevant task spec before writing any code.

---

## Purpose

Task specifications serve multiple purposes:

1. **Alignment:** Ensure engineers and AI agents implement exactly what was scoped.
2. **Context:** Provide the "why" behind a feature so implementation decisions are correct.
3. **Traceability:** Link implementation commits and PRs back to their requirements.
4. **Review:** Provide reviewers with the acceptance criteria to validate against.

---

## File Naming Convention

```
TASK-{number}-{short-title}.md
```

Examples:
- `TASK-001-repository-initialization.md`
- `TASK-002-api-bootstrap.md`
- `TASK-003-flutter-bootstrap.md`
- `TASK-004-auth-module.md`

Numbers are sequential. Task files are never deleted — completed tasks are marked with their
completion date and PR reference.

---

## Task Specification Template

```markdown
# TASK-{number} — {Title}

**Status:** Pending | In Progress | Complete
**Phase:** {milestone or phase name}
**Completed:** {date} | —
**PR:** #{number} | —

## Objective

What does this task accomplish? (2-3 sentences)

## Scope

What is explicitly IN scope for this task?

## Out of Scope

What is explicitly NOT included in this task?
(This prevents scope creep during implementation)

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] ...

## Technical Notes

Architecture constraints, patterns to use, references to ADRs or CLAUDE.md sections.

## Files Affected

Expected files to be created or modified.

## Dependencies

Other tasks that must be complete before this task starts.
```

---

## Task Index

| Task | Title | Status |
|---|---|---|
| [TASK-001](TASK-001.md) | Repository Initialization & Engineering Workspace | Complete |
| [TASK-002](TASK-002.md) | Development Infrastructure (Docker, Compose, Config, Health) | Complete |
| [TASK-003](TASK-003.md) | FastAPI Foundation (Backend Skeleton) | Complete |

---

## Process

1. A task specification is created before any implementation begins.
2. The engineer (or AI agent) reads the specification completely before writing code.
3. Implementation follows the spec — deviations require discussion before proceeding.
4. On PR merge, the task status is updated to Complete with the PR reference.
