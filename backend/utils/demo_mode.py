from fastapi import HTTPException, Request
from fastapi.routing import APIRoute

from backend import config, models
from backend.constants import DEMO_USER_EMAILS


def is_demo_mode() -> bool:
    return config.DEMO_MODE


def require_demo_mode() -> None:
    if not is_demo_mode():
        raise HTTPException(status_code=404, detail="Not found")


def _raise_demo_restricted_action(action: str) -> None:
    raise HTTPException(
        status_code=403,
        detail={
            "code": "DEMO_RESTRICTED_ACTION",
            "message": "This action is unavailable in the public demo.",
            "action": action,
        },
    )


def reject_demo_restricted_action(current_user: models.User, action: str) -> None:
    """Protect only the explicitly mapped public demo identities."""
    if is_demo_mode() and current_user.email in DEMO_USER_EMAILS.values():
        _raise_demo_restricted_action(action)


class AccountEntryRoute(APIRoute):
    """Reject ordinary account entry in demo mode before parsing or probing."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def guarded_handler(request: Request):
            if is_demo_mode():
                _raise_demo_restricted_action("account_entry")
            return await handler(request)

        return guarded_handler


class DemoModeRoute(APIRoute):
    """Gate demo-only endpoints before FastAPI reads or parses the body."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def guarded_handler(request: Request):
            require_demo_mode()
            return await handler(request)

        return guarded_handler


class DemoAIRoute(APIRoute):
    """Public V1 has no worker or external diagnostics; hide them before parsing."""

    def get_route_handler(self):
        handler = super().get_route_handler()
        unsupported = self.path in {
            "/ai/chat", "/ai/chat/async", "/ai/recommend-providers",
        } or self.path.startswith(("/ai/health/", "/ai/tasks", "/ai/milvus/"))

        async def guarded_handler(request: Request):
            if is_demo_mode() and unsupported:
                raise HTTPException(status_code=404, detail="Not found")
            return await handler(request)

        return guarded_handler
