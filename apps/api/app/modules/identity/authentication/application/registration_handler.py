"""
Registration command handler — CQRS entry point.

Provides the command-handler facade that a future command bus or API
router will call. Separating the handler from the service allows:
  - Multiple handlers to wrap the same service (CLI, API, background job).
  - A command bus to dispatch RegisterUserCommand to this handler via
    reflection without coupling to the service directly.
  - Cross-cutting concerns (logging, metrics) to be applied here without
    polluting the service.

Current implementation:
  The handler is a thin delegation wrapper. The RegistrationService owns all
  the orchestration logic. This keeps the handler stateless and free of
  business decisions.

Future OAuth / passkey handlers:
  When OAuth registration is implemented, an OAuthRegisterHandler will
  be added alongside this handler. A RegistrationHandlerRouter would
  dispatch RegisterUserCommand to the correct handler based on the
  command type discriminator.
"""

from __future__ import annotations

import logging

from app.modules.identity.authentication.application.commands import RegisterUserCommand
from app.modules.identity.authentication.application.dtos import RegistrationResult
from app.modules.identity.authentication.application.registration_service import (
    RegistrationService,
)

logger = logging.getLogger(__name__)


class RegisterUserHandler:
    """
    CQRS command handler for RegisterUserCommand.

    Dispatches the command to the RegistrationService and returns the
    RegistrationResult. Owns no business logic.

    Usage (FastAPI route):
        handler = Depends(get_registration_handler)

        @router.post("/register")
        async def register(
            body: RegisterRequest,
            handler: CurrentRegistrationHandler,
        ) -> RegisterResponse:
            command = RegisterUserCommand(email=body.email, password=body.password)
            result = await handler.handle(command)
            match result:
                case Success(value=summary):
                    return RegisterResponse(...)
                case Failure(error=err):
                    raise_http_for(err)
    """

    def __init__(self, service: RegistrationService) -> None:
        self._service = service

    async def handle(self, command: RegisterUserCommand) -> RegistrationResult:
        """
        Handle a RegisterUserCommand.

        Delegates entirely to RegistrationService.execute(). Returns the
        RegistrationResult directly — no exception translation here.
        """
        return await self._service.execute(command)
