# Travel Planning Bounded Context

The Travel Planning feature module provides AI-powered trip proposal generation. Users request a travel plan for an existing Trip, and the system orchestrates plan generation via an AI service abstraction. The result is persisted as a `TripProposal` aggregate.

## Domain Model

### TripProposal (Aggregate Root)
Manages the lifecycle of an AI-generated proposal.
- **Identity**: `ProposalId` (UUID)
- **Status lifecycle**:
  - `QUEUED`: Request has been submitted.
  - `GENERATING`: AI engine is processing the request.
  - `READY`: Generation completed successfully; proposal contains the recommended plan and an expiration timestamp (default: 24 hours).
  - `ACCEPTED`: User accepted the plan.
  - `REJECTED`: User rejected the plan.
  - `FAILED`: Generation failed (AI error) or was superseded by a newer proposal.
  - `EXPIRED`: Proposal passed its TTL.

### Value Objects
- `PlanningPreferences`: Flat user criteria (destination, duration, budget tier, interest tags, travel style, custom requirements).
- `PlanningResult`: Flattened structured AI recommendations (summary, estimated cost, day-by-day suggested activities).
- `ProposedDay`: A single day containing sequential proposed activities.
- `ProposedActivity`: A single scheduled suggestion (title, description, category, duration, cost).

## Architecture

1. **AI Service Abstraction (`app/services/ai/`)**:
   Uses the `PlanningEngine` Protocol interface. Under local dev and testing, `MockPlanningEngine` generates deterministic travel proposals without requiring API keys.
2. **CQRS & Service (`application/`)**:
   Standard commands and queries (e.g. `RequestProposalCommand`, `GetProposalQuery`) are dispatched to `PlanningService` via specialized CQRS handlers.
3. **Optimistic Locking**:
   Version checking is automatically managed via SQLAlchemy's `version` mapping to protect against concurrent updates.
4. **Lazy Expiration**:
   When queried, proposals in `READY` status check if the current time exceeds `expires_at`. If so, they are lazily marked as `EXPIRED` in database.

## Presentation Layer (API Endpoints)

- `POST /api/v1/trips/{trip_id}/planning/proposals` — Request a new proposal
- `GET /api/v1/planning/proposals/{proposal_id}` — Get proposal by ID
- `GET /api/v1/trips/{trip_id}/planning/proposals` — Get the latest proposal for a trip
- `POST /api/v1/planning/proposals/{proposal_id}/accept` — Accept proposal
- `POST /api/v1/planning/proposals/{proposal_id}/reject` — Reject proposal
- `GET /api/v1/planning/proposals` — List proposals with cursor-based pagination
