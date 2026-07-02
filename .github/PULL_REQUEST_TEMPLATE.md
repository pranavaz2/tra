## Summary

<!-- 
Provide a clear, concise summary of what this PR does and WHY.
What problem does it solve? What feature does it add?
Link to the task specification in docs/tasks/ if applicable.
-->

**Task Spec:** `docs/tasks/` <!-- link to spec file if applicable -->
**Issue:** <!-- #issue-number if applicable -->

---

## Changes Made

<!--
List the specific changes in this PR. Be concrete.
- What was added?
- What was changed?
- What was removed?
-->

-
-
-

---

## Type of Change

<!-- Check all that apply -->

- [ ] `feat` — New feature
- [ ] `fix` — Bug fix
- [ ] `refactor` — Code restructure (no behavior change)
- [ ] `chore` — Maintenance / dependency update
- [ ] `docs` — Documentation only
- [ ] `test` — Tests only
- [ ] `ci` — CI/CD changes
- [ ] `security` — Security improvement
- [ ] `perf` — Performance improvement
- [ ] `BREAKING CHANGE` — This change breaks the existing API or contract

---

## Architecture Compliance

<!-- Confirm compliance with CLAUDE.md -->

- [ ] No business logic was added to Flutter
- [ ] All external service calls go through the abstraction layer in `app/services/`
- [ ] Module boundaries are respected — no circular imports introduced
- [ ] Naming conventions in CLAUDE.md Section 8 are followed
- [ ] No secrets or API keys are present in any file
- [ ] `os.environ` is not used directly in application code

---

## Database Changes

<!-- Complete this section only if the database schema was changed -->

- [ ] Not applicable — no schema changes in this PR
- [ ] A new Alembic migration was created (existing migrations not modified)
- [ ] PostGIS geometry columns have GiST indexes in the migration
- [ ] Soft-delete column (`deleted_at`) added for new user-facing entities
- [ ] `created_at` and `updated_at` columns present on new tables
- [ ] Foreign key `ON DELETE` behavior explicitly defined

---

## API Changes

<!-- Complete this section only if API endpoints were added or modified -->

- [ ] Not applicable — no API changes in this PR
- [ ] All new routes are prefixed `/api/v1/`
- [ ] All endpoints have Pydantic request and response models
- [ ] Error responses follow RFC 7807 Problem Details format
- [ ] Authentication is applied (or endpoint is explicitly public)
- [ ] Rate limiting applied to AI-backed endpoints

---

## Testing

<!-- Describe how you tested this change -->

**Unit tests:**
- [ ] Written and passing
- [ ] Not required (explain why below)

**Integration tests:**
- [ ] Written and passing
- [ ] Not required (explain why below)

**Manual testing performed:**
<!-- Describe what you manually tested -->

---

## Code Quality

- [ ] `ruff check .` passes with zero violations (Python changes)
- [ ] `black --check .` passes with no changes (Python changes)
- [ ] `dart analyze` passes with zero issues (Flutter changes)
- [ ] `dart format --check .` passes with no changes (Flutter changes)
- [ ] `pre-commit run --all-files` passes locally

---

## Documentation

- [ ] Not applicable
- [ ] CLAUDE.md updated (if architectural rules changed)
- [ ] ADR created in `docs/adr/` (if a significant architectural decision was made)
- [ ] `.env.example` updated (if new environment variables were added)
- [ ] Task specification in `docs/tasks/` marked complete

---

## Breaking Changes

<!-- If this is a breaking change, describe the impact and migration path -->

- [ ] No breaking changes
- [ ] Breaking change — describe impact and migration path below:

<!-- Migration path: -->

---

## Checklist Before Merge

- [ ] PR title follows Conventional Commits format (`type(scope): description`)
- [ ] All CI checks are passing
- [ ] All review conversations are resolved
- [ ] Self-review of the diff completed — no debug code, no commented-out code
- [ ] Definition of Done checklist in CLAUDE.md Section 16 is complete
