"""
Travix AI — Infrastructure Abstractions (Shared Kernel)

Vendor-neutral interfaces for infrastructure concerns used across all modules.
Default implementations use Python stdlib only — no third-party dependencies.

These interfaces make infrastructure concerns testable:
  - Replace SystemClock with a FixedClock in tests for deterministic time.
  - Replace DefaultUuidProvider with a SequentialUuidProvider for predictable IDs.
  - Replace DefaultRandomProvider with a SeededRandomProvider for reproducible tests.

Concrete vendor implementations (Redis, S3, etc.) live in app/services/.
"""
