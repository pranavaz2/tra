# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.x     | Yes       |

Only the latest release branch receives security fixes. Older branches are not supported.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Security issues can expose user data or allow unauthorized access to the platform. Please
report them privately so they can be addressed before public disclosure.

### How to Report

Email the security team at: **security@travixai.com**

Include the following in your report:

- A description of the vulnerability and its potential impact
- Steps to reproduce the issue (proof-of-concept code is welcome)
- The component or endpoint affected
- Any suggested mitigations

We will acknowledge your report within **48 hours** and provide a resolution timeline within
**7 business days**.

## Disclosure Policy

Travix AI follows **coordinated disclosure**:

1. You report the issue privately.
2. We investigate and develop a fix.
3. We release the fix and publish a security advisory.
4. You may disclose the vulnerability publicly after the fix is released, or after 90 days
   from your initial report (whichever comes first).

We will credit you in the security advisory unless you prefer to remain anonymous.

## Security Design

Key security controls implemented in Travix AI:

- **JWT access tokens** expire after 15 minutes.
- **Refresh token rotation** — each use issues a new token and revokes the previous one.
  Reuse of a superseded token triggers immediate revocation of the entire token family
  (stolen token detection).
- **Redis-backed token revocation** — logout and suspicious activity revoke tokens immediately,
  without waiting for natural expiry.
- **Input validation** — all user input is validated at the API boundary via Pydantic v2.
  No raw user data reaches business logic or the database.
- **AI prompt injection prevention** — user-supplied text is always passed as data values in
  prompt templates, never interpolated directly into instruction text.
- **Secrets management** — credentials are stored in environment variables and never committed
  to the repository.
- **Non-root containers** — all Docker containers run as a non-root `travix` user (UID 1001).
- **CORS** — explicitly configured per environment; `*` is never permitted in production.
- **Soft deletes** — user data is never hard-deleted without an explicit data deletion request.

## Scope

This policy covers:

- The Travix AI API (`apps/api/`)
- The Travix AI mobile application (`apps/mobile/`)
- The infrastructure configuration in this repository

It does not cover third-party services integrated with Travix AI (Google Maps, OpenAI, etc.).
Report vulnerabilities in those services directly to their maintainers.
