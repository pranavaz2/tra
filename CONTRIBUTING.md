# Contributing to Travix AI

This document defines the development workflow, branching conventions, commit standards, and
code review expectations for all contributors to Travix AI.

All contributors — human and AI — must follow these conventions. Consistency is what makes a
codebase maintainable at scale.

---

## Table of Contents

1. [Development Environment](#1-development-environment)
2. [Branch Naming](#2-branch-naming)
3. [Commit Conventions](#3-commit-conventions)
4. [Pull Request Process](#4-pull-request-process)
5. [Code Review Expectations](#5-code-review-expectations)
6. [Development Workflow](#6-development-workflow)
7. [Definition of Done](#7-definition-of-done)

---

## 1. Development Environment

### Prerequisites

| Tool | Minimum Version | Purpose |
|---|---|---|
| Docker | 24+ | Container runtime |
| Docker Compose | v2 (plugin) | Local orchestration |
| Flutter SDK | Stable channel | Mobile development |
| Python | 3.12+ | Backend development |
| Make | 4+ | Developer task runner |
| pre-commit | 3+ | Git hook management |
| Git | 2.40+ | Version control |

### First-Time Setup

```bash
# 1. Clone the repository
git clone https://github.com/travix-ai/travix-ai.git
cd travix-ai

# 2. Copy and configure environment variables
cp .env.example .env
# Edit .env — fill in required values for local development

# 3. Install pre-commit hooks
pip install pre-commit
pre-commit install

# 4. Run the full setup
make setup

# 5. Start infrastructure services
make docker-up

# 6. Apply database migrations
make migrate

# 7. Verify everything works
make test
```

---

## 2. Branch Naming

All branches follow the Conventional Branch naming pattern:

```
<type>/<scope>-<short-description>
```

### Types

| Type | When to Use |
|---|---|
| `feat` | New feature or functionality |
| `fix` | Bug fix |
| `chore` | Maintenance, dependency updates, config changes |
| `docs` | Documentation changes only |
| `refactor` | Code restructuring with no behavior change |
| `test` | Adding or fixing tests only |
| `ci` | CI/CD pipeline changes |
| `perf` | Performance improvements |
| `security` | Security-related changes |

### Scope (optional but recommended)

Scope identifies which part of the system is affected:

- `api` — backend changes
- `mobile` — Flutter changes
- `infra` — infrastructure changes
- `auth` — authentication system
- `trips` — trip planning module
- `maps` — maps integration
- `ai` — AI integration
- `db` — database migrations only

### Examples

```
feat/api-trip-planning-module
fix/mobile-auth-token-refresh
chore/update-python-dependencies
docs/adr-ai-provider-selection
refactor/api-trip-repository
test/api-trip-service-unit-tests
ci/add-flutter-lint-workflow
security/refresh-token-rotation
```

### Rules

- Use lowercase only
- Use hyphens, not underscores or spaces
- Keep descriptions short but descriptive (3–5 words)
- Branch off from `main` unless explicitly working from a feature branch
- Delete branches after merge — no stale branches

---

## 3. Commit Conventions

All commits follow the [Conventional Commits 1.0.0](https://www.conventionalcommits.org/)
specification.

### Format

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### Rules

- The **description** is in imperative mood: "add trip model" not "added trip model"
- The **description** is lowercase, no period at the end
- The **body** explains the **why**, not the what (the diff already shows the what)
- **Breaking changes** are indicated by `BREAKING CHANGE:` in the footer or `!` after the type
- Keep the description under 72 characters
- Keep commits atomic — one logical change per commit

### Types

| Type | Description |
|---|---|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation changes only |
| `style` | Formatting changes (no logic change) |
| `refactor` | Code restructure without feature change or bug fix |
| `test` | Adding or updating tests |
| `chore` | Build process, dependencies, config |
| `perf` | Performance improvement |
| `ci` | CI/CD changes |
| `security` | Security fix or improvement |
| `revert` | Reverts a previous commit |

### Examples

```
feat(api): add trip creation endpoint

fix(mobile): resolve token refresh race condition

docs(adr): add ADR-003 for AI provider selection

chore(api): update FastAPI to 0.115.0

feat(api)!: change trip response schema to include nested destinations

BREAKING CHANGE: TripResponse now includes a `destinations` array.
Clients must update to handle the new schema.

test(api): add integration tests for trip repository

refactor(mobile): extract trip card into shared widget
```

---

## 4. Pull Request Process

### Before Opening a PR

- [ ] All pre-commit hooks pass locally (`pre-commit run --all-files`)
- [ ] All tests pass (`make test`)
- [ ] `dart analyze` passes with zero issues (Flutter changes)
- [ ] `ruff check .` passes with zero issues (Python changes)
- [ ] The Definition of Done checklist (Section 7) is complete

### PR Size Guidelines

Keep pull requests **small and focused**. A PR should represent one logical unit of change.

| Size | Lines Changed | Guideline |
|---|---|---|
| Small | < 200 | Ideal — fast to review |
| Medium | 200–500 | Acceptable — provide clear context |
| Large | 500–1000 | Justify in the PR description |
| Too large | > 1000 | Break into smaller PRs |

### PR Title

Follow the same Conventional Commits format as commit messages:

```
feat(api): add trip planning service

fix(mobile): resolve null safety issue in trip card
```

### Draft PRs

Open a draft PR early for:

- Work in progress that needs visibility
- Large features being built incrementally
- When you want early feedback on approach

Convert to ready when the Definition of Done is complete.

### Target Branch

All PRs target `main`. Direct pushes to `main` are disabled.

---

## 5. Code Review Expectations

### For Authors

- Provide enough context in the PR description that a reviewer can understand the change
  without asking questions
- Respond to all review comments before requesting re-review
- Don't merge with unresolved conversations
- Don't resolve other people's comments — only the commenter should resolve their own

### For Reviewers

Reviews must check for:

**Correctness**
- Does the implementation match the task specification?
- Are edge cases handled?
- Are there obvious bugs?

**Architecture**
- Does the code comply with CLAUDE.md?
- Are module boundaries respected?
- Is business logic in the right layer?
- Are external services accessed through abstractions?

**Security**
- No hardcoded secrets or credentials
- User input validated at the API boundary
- Authentication applied to all appropriate endpoints
- No SQL injection risk (raw queries are parameterized)

**Quality**
- Type hints present on all Python functions
- Zero `dart analyze` warnings
- Tests are present and meaningful (not just coverage padding)
- Naming follows conventions in CLAUDE.md Section 8

### Review SLA

- **First review:** within 1 business day of PR submission
- **Follow-up reviews:** within 4 hours of re-review request

### Approval Requirements

- Minimum 1 approval required before merge
- All CI checks must pass
- No unresolved review conversations

---

## 6. Development Workflow

```
main (always deployable)
  │
  └── feat/api-trip-module    ← your branch
        │
        ├── commit: feat(api): add trip model
        ├── commit: feat(api): add trip repository
        ├── commit: feat(api): add trip service
        ├── commit: test(api): add trip service unit tests
        └── commit: feat(api): add trip router
              │
              └── Pull Request → review → merge to main
```

### Day-to-Day Workflow

```bash
# 1. Start from latest main
git checkout main
git pull origin main

# 2. Create your branch
git checkout -b feat/api-trip-planning-module

# 3. Make changes, commit frequently
git add apps/api/app/modules/trips/
git commit -m "feat(api): add trip SQLAlchemy model"

# 4. Keep your branch up to date
git fetch origin
git rebase origin/main

# 5. Push and open a PR
git push -u origin feat/api-trip-planning-module
# Open PR via GitHub

# 6. After merge, clean up
git checkout main
git pull origin main
git branch -d feat/api-trip-planning-module
```

### Rebase vs Merge

- **Always rebase** to update your branch with `main` — never merge `main` into your branch.
- The merge into `main` uses a **squash merge** when the commit history is noisy, or
  **merge commit** when the commit history tells a coherent story.

---

## 7. Definition of Done

See [CLAUDE.md](CLAUDE.md) Section 16 for the complete Definition of Done checklist.

All items must be checked before a PR is marked ready for review.
