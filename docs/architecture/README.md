# docs/architecture/ — System Architecture

This folder contains **system architecture documentation** for Travix AI — high-level
descriptions of the system design, component relationships, data flows, and infrastructure
layout.

---

## Purpose

Architecture documentation translates the principles in `CLAUDE.md` into concrete descriptions
of how the system is actually structured. It provides the mental model that engineers need to
understand where new code belongs, how data flows between components, and how the system
behaves under different conditions.

---

## Contents

This folder will contain:

| Document | Purpose |
|---|---|
| `overview.md` | System-level architecture narrative |
| `backend-modules.md` | FastAPI module structure and boundaries |
| `flutter-structure.md` | Flutter feature structure and layer separation |
| `service-abstractions.md` | External service abstraction layer design |
| `auth-flow.md` | Authentication and token lifecycle |
| `ai-orchestration.md` | AI task flow and async job design |
| `offline-sync.md` | Offline-first sync strategy and conflict resolution |
| `database-schema.md` | Entity relationships and database design decisions |
| `infrastructure.md` | Docker, networking, and environment configuration |

---

## Key Architecture Principles

This documentation reflects the following non-negotiable principles (defined in `CLAUDE.md`):

- **Clean Architecture:** Dependencies flow inward. The domain layer has no external dependencies.
- **Vertical Slice Architecture:** Code organized by feature, not by layer.
- **Modular Monolith:** Single deployable unit with enforced module boundaries.
- **Backend owns business logic:** Flutter is display-only.
- **Every external service behind an abstraction:** No vendor lock-in.

---

## Status

> Architecture documents will be added as each system component is designed and implemented.
> The source of truth for architectural rules is always `CLAUDE.md`.
