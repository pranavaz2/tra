"""
Rate Limit Headers — extension point for HTTP rate limiting responses.

Provides typed structures and header-building utilities for the standard
rate limit response headers. No rate limiting enforcement is implemented
here — this module only prepares the plumbing.

Standard headers supported:
    RateLimit-Limit      — maximum requests allowed in the current window.
    RateLimit-Remaining  — requests remaining in the current window.
    RateLimit-Reset      — UTC epoch seconds when the window resets.
    Retry-After          — seconds to wait before retrying (used on 429 responses).

These header names follow the IETF draft-ietf-httpapi-ratelimit-headers spec.
When the spec is finalised, these names may be standardised.

Planned integration points (TASK-3.x — Rate Limiting):
    1. A Redis-backed rate limiter (token bucket or sliding window) tracks
       request counts per (user_id | ip_address) × endpoint.
    2. The rate limiter calls build_rate_limit_headers() and the result is
       attached to every response in a RateLimitMiddleware.
    3. On limit exceeded (429), the response includes Retry-After.

Usage today (forward-compatible):
    # In a route handler or middleware:
    info = RateLimitInfo(limit=60, remaining=59, reset_at=1700000000)
    headers = build_rate_limit_headers(info)
    # headers = {"RateLimit-Limit": "60", "RateLimit-Remaining": "59",
    #             "RateLimit-Reset": "1700000000"}

Usage on 429 (planned):
    info = RateLimitInfo(limit=60, remaining=0, reset_at=1700000060, retry_after=60)
    return JSONResponse(status_code=429, content=body,
                        headers=build_rate_limit_headers(info))
"""

from __future__ import annotations

from dataclasses import dataclass, field

RATE_LIMIT_LIMIT_HEADER = "RateLimit-Limit"
RATE_LIMIT_REMAINING_HEADER = "RateLimit-Remaining"
RATE_LIMIT_RESET_HEADER = "RateLimit-Reset"
RETRY_AFTER_HEADER = "Retry-After"


@dataclass(frozen=True)
class RateLimitInfo:
    """
    Rate limit state for the current request window.

    Attributes:
        limit:       Maximum number of requests permitted in the window.
        remaining:   Requests remaining before the limit is reached.
        reset_at:    UTC epoch seconds when the window resets and remaining
                     returns to limit. Use int(datetime.now(UTC).timestamp()) + window.
        retry_after: Seconds the client must wait before retrying.
                     None means the limit has not been exceeded yet.
                     Set this to reset_at - now when returning 429.
        policy:      Human-readable label for the policy that applies
                     (e.g., "login", "ai-generation"). Included in the
                     RateLimit-Policy extension header (IETF draft).
    """

    limit: int
    remaining: int
    reset_at: int           # UTC epoch seconds
    retry_after: int | None = None
    policy: str | None = None


def build_rate_limit_headers(info: RateLimitInfo) -> dict[str, str]:
    """
    Build the dict of rate limit response headers from a RateLimitInfo.

    Returns a dict suitable for passing as the `headers` argument to
    JSONResponse or for merging into an existing response headers dict.

    Always includes:
        RateLimit-Limit
        RateLimit-Remaining
        RateLimit-Reset

    Conditionally includes:
        Retry-After        — only when info.retry_after is not None (on 429).
    """
    headers: dict[str, str] = {
        RATE_LIMIT_LIMIT_HEADER: str(info.limit),
        RATE_LIMIT_REMAINING_HEADER: str(info.remaining),
        RATE_LIMIT_RESET_HEADER: str(info.reset_at),
    }
    if info.retry_after is not None:
        headers[RETRY_AFTER_HEADER] = str(info.retry_after)
    return headers


def exceeded(info: RateLimitInfo) -> bool:
    """Return True if the rate limit has been reached (remaining == 0)."""
    return info.remaining <= 0


@dataclass(frozen=True)
class RateLimitPolicy:
    """
    Named rate limit policy definition.

    Specifies how many requests are allowed per window for a given scope.
    Used by the rate limiter implementation (TASK-3.x) to look up the
    applicable policy for a request type.

    Attributes:
        name:         Policy identifier used as the RateLimit-Policy label.
        limit:        Maximum requests per window.
        window_secs:  Duration of the counting window in seconds.
        scope:        What the limit applies to ("user", "ip", "global").
    """

    name: str
    limit: int
    window_secs: int
    scope: str = "user"
    _reserved: None = field(default=None, repr=False)


# Pre-defined policy names — concrete policies are wired in TASK-3.x.
POLICY_LOGIN = "login"                    # Prevent brute-force
POLICY_REGISTRATION = "registration"     # Prevent account farming
POLICY_AI_GENERATION = "ai-generation"   # Expensive GPU ops
POLICY_REFRESH = "refresh"               # Prevent token thrashing
POLICY_DEFAULT = "default"               # Catch-all
