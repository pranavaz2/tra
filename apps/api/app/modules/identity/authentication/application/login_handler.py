"""
Login command handler — CQRS entry point.

Provides the command-handler facade that a future command bus or API
router will call. Separating the handler from the service allows:
  - Multiple handlers to wrap the same service (CLI, API, background job).
  - A command bus to dispatch LoginUserCommand to this handler via
    reflection without coupling to the service directly.
  - Cross-cutting concerns (logging, metrics) to be applied here without
    polluting the service.

Current implementation:
  The handler is a thin delegation wrapper. The LoginService owns all the
  orchestration logic. This keeps the handler stateless and free of
  business decisions.

Future OAuth / passkey handlers:
  When OAuth login is implemented, an OAuthLoginHandler will be added
  alongside this handler. A LoginHandlerRouter would dispatch based on the
  command type discriminator, selecting:
    LoginUserHandler    — for LoginUserCommand (password)
    OAuthLoginHandler   — for OAuthLoginCommand (provider token)
    PasskeyLoginHandler — for PasskeyLoginCommand (WebAuthn assertion)
"""

from __future__ import annotations

import logging

from app.modules.identity.authentication.application.commands import LoginUserCommand
from app.modules.identity.authentication.application.dtos import LoginResult
from app.modules.identity.authentication.application.login_service import LoginService

logger = logging.getLogger(__name__)


class LoginUserHandler:
    """
    CQRS command handler for LoginUserCommand.

    Dispatches the command to the LoginService and returns the LoginResult.
    Owns no business logic.

    Usage (FastAPI route):
        handler = Depends(get_login_handler)

        @router.post("/login")
        async def login(
            body: LoginRequest,
            handler: CurrentLoginHandler,
        ) -> LoginResponse:
            command = LoginUserCommand(email=body.email, password=body.password)
            result = await handler.handle(command)
            match result:
                case Success(value=summary):
                    return LoginResponse(...)
                case Failure(error=err):
                    raise_http_for(err)
    """

    def __init__(self, service: LoginService) -> None:
        self._service = service

    async def handle(self, command: LoginUserCommand) -> LoginResult:
        """
        Handle a LoginUserCommand.

        Delegates entirely to LoginService.execute(). Returns the
        LoginResult directly — no exception translation here.
        """
        return await self._service.execute(command)
