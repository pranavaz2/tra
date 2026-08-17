# Travel Context

The Travel bounded context is the core of Travix AI.

It owns every domain concept related to planning, executing, and reflecting on a trip.

## Modules

| Module | Responsibility |
|---|---|
| `trips/` | Trip lifecycle — creation, status, metadata, privacy |
| `itinerary/` | Day-by-day activity schedule and travel segments |
| `locations/` | Canonical reference data for places, cities, regions, countries |
| `search/` | Text search, autocomplete, and nearby discovery |
| `planning/` | Orchestrates AI proposal generation pipeline |
| `constraint_engine/` | Feasibility validation via composable rules |
| `optimization_engine/` | Route and schedule optimization |
| `ai_enhancement/` | LLM-backed suggestion and content enrichment |
| `environmental/` | Weather, air quality, UV index, sunrise/sunset |
| `cost_estimation/` | Predictive cost ranges before a trip is booked |
| `preferences/` | User travel preferences consumed across all modules |
| `budget/` | Actual spending, expenses, and budget categories |
| `recommendations/` | Personalized place and trip suggestions |
| `sharing/` | Collaboration, member roles, and public share links |
| `media/` | Photos, notes, and voice memos attached to trips |
| `offline/` | Client sync protocol and conflict resolution |
| `notifications/` | Multi-channel alert routing |
| `projections/` | Denormalized read models for list and summary queries |
| `analytics/` | Event consumer — telemetry only, no domain state |

## Architecture rules

- Modules communicate only through the EventBus or explicit Protocol interfaces.
- No module imports another module's repository or aggregate directly.
- The Shared Kernel provides value objects, domain event envelopes, `Result[T]`, and `TravixError`.
- Identity is consumed via `UserId` and `SessionId` value objects only.
