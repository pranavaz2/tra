"""
Travix AI — Core Middleware

Cross-cutting ASGI middleware applied to every request.
All middleware is registered in app.main.create_app().

Execution order on inbound requests (first to last):
  RequestIDMiddleware     → assigns request_id / correlation_id to ContextVars
  TimingMiddleware        → starts response timer
  SecurityHeadersMiddleware → adds security headers on the way out
  CORSMiddleware          → handles CORS preflight and response headers

Note: FastAPI/Starlette applies middleware in reverse registration order.
The last add_middleware() call in create_app() runs first on requests.
"""
