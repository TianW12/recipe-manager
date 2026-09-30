"""Shared template engine + base path, imported by every route module."""

from pathlib import Path

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

# Directory of the app package; static/ and templates/ live under it.
BASE = Path(__file__).resolve().parent


def _auth_context(request: Request) -> dict:
    """Make ``user`` available in every template without passing it manually."""
    from .security import current_user  # local import avoids a circular import

    return {"user": current_user(request)}


templates = Jinja2Templates(
    directory=BASE / "templates", context_processors=[_auth_context]
)
