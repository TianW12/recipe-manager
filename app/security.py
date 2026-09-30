"""Password hashing + session helpers for the login system.

Passwords are hashed with bcrypt (slow by design, salted per password), so the
database never stores a password — only a hash that cannot be reversed.

"Being logged in" = the user's id stored in the session cookie. The cookie is
signed by SessionMiddleware with SECRET_KEY, so it cannot be forged or edited
by the client.
"""

import os
import secrets

import bcrypt
from fastapi import Request

from .db import DB_PATH
from . import repository


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def get_secret_key() -> str:
    """Key used to sign session cookies.

    Prefer the SECRET_KEY environment variable (set it in production). Otherwise
    generate one once and persist it next to the database, so sessions survive
    restarts on the Pi without any configuration.
    """
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    key_file = DB_PATH.parent / ".secret_key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_hex(32)
    key_file.write_text(key)
    return key


def current_user(request: Request):
    """Return the logged-in user's row, or None if not logged in."""
    uid = request.session.get("user_id")
    if uid is None:
        return None
    return repository.get_user_by_id(uid)
