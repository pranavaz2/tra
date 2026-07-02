"""
DeviceTrust — the inferred trust level of a client device.

Assigned by the risk assessment layer (TASK-2.x / TASK-3.x) based on
device history and behavioural signals. Stored as a string so it can be
persisted and included in JWT claims without a mapping layer.

Architecture:
  No risk engine is implemented in this sprint. DeviceTrust is an
  architectural extension point only. Values flow into:
    - SecurityContext.device_trust_level (all requests)
    - AuthenticationSession metadata (future)
    - RiskDecision signals (future)

Transitions (typical):
  UNKNOWN → NEW          first time a device_id is seen for this user
  NEW → TRUSTED          after N successful logins from the same device
  TRUSTED → SUSPICIOUS   if impossible-travel or proxy signals fire
  * → SUSPICIOUS         on any security anomaly detection
"""

from __future__ import annotations

from enum import Enum


class DeviceTrust(str, Enum):
    """
    Trust classification for a client device making an authentication request.

    UNKNOWN     — device_id not provided or not yet seen.
    NEW         — device_id seen for the first time for this user.
    TRUSTED     — device has a positive history with this user account.
    SUSPICIOUS  — device or network has triggered a security signal.
    """

    UNKNOWN = "unknown"
    NEW = "new"
    TRUSTED = "trusted"
    SUSPICIOUS = "suspicious"
