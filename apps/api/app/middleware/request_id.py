# Canonical location: app.core.middleware.request_id
# This module is a compatibility shim — import from the canonical path instead.
from app.core.middleware.request_id import (  # noqa: F401
    CORRELATION_ID_HEADER,
    REQUEST_ID_HEADER,
    RequestIDMiddleware,
    get_correlation_id,
    get_request_id,
    set_correlation_id,
)
