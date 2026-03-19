import os
from functools import wraps

from authlib.integrations.starlette_client import OAuth
from fastapi import Request
from fastapi.responses import RedirectResponse

oauth = OAuth()

# Only register Google OAuth if credentials are set
_google_configured = bool(os.getenv("GOOGLE_CLIENT_ID"))

if _google_configured:
    oauth.register(
        name="google",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def is_google_configured() -> bool:
    return _google_configured


def get_current_user_id(request: Request) -> int | None:
    """Get user_id from session, or None if not logged in."""
    return request.session.get("user_id")


def require_login(request: Request) -> int | None:
    """Returns user_id if logged in, None otherwise (caller should redirect)."""
    return get_current_user_id(request)
