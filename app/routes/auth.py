"""Login / register / logout / email verification pages.

Email is the login identifier (unique, case-insensitive); username is just an
optional display name.

Verification flow: registering (or logging in unverified) emails a 6-digit
code and sends the user to /verify. Only the sha256 of the code is stored,
it expires after 15 minutes, and 5 wrong guesses invalidate it. The pending
user id lives in the session under ``pending_uid`` — a real login session
(``user_id``) is only created after the code checks out.
"""

import hashlib
import secrets
import sqlite3

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import emailer, repository
from ..security import hash_password, verify_password
from ..templating import templates

router = APIRouter()


def _issue_code(user) -> None:
    """Generate a fresh 6-digit code, store its hash, email it to the user."""
    code = f"{secrets.randbelow(10**6):06d}"
    repository.set_email_code(
        user["id"], hashlib.sha256(code.encode()).hexdigest()
    )
    emailer.send_verification_code(user["email"], code)


def _start_verification(request: Request, user) -> RedirectResponse:
    _issue_code(user)
    request.session.clear()
    request.session["pending_uid"] = user["id"]
    return RedirectResponse("/verify", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "", "email": ""}
    )


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = repository.get_user_by_email(email.strip())
    # Same error for "no such user" and "wrong password" so an attacker can't
    # probe which emails are registered.
    if user is None or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password.", "email": email},
            status_code=401,
        )
    if not user["verified"]:
        return _start_verification(request, user)
    request.session["user_id"] = user["id"]
    return RedirectResponse("/", status_code=303)


@router.get("/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "error": "", "email": "", "username": ""},
    )


@router.post("/register")
def register(
    request: Request,
    email: str = Form(...),
    username: str = Form(""),
    password: str = Form(...),
    password2: str = Form(...),
):
    email = email.strip()
    error = ""
    if "@" not in email or "." not in email.split("@")[-1]:
        error = "Please enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif password != password2:
        error = "Passwords do not match."
    if not error:
        try:
            uid = repository.create_user(email, username.strip(), hash_password(password))
        except sqlite3.IntegrityError:  # UNIQUE constraint on email
            error = "That email is already registered."
        else:
            return _start_verification(request, repository.get_user_by_id(uid))
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "error": error, "email": email, "username": username},
        status_code=400,
    )


@router.get("/verify", response_class=HTMLResponse)
def verify_form(request: Request):
    user = _pending_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        "verify.html", {"request": request, "error": "", "email": user["email"]}
    )


@router.post("/verify")
def verify(request: Request, code: str = Form(...)):
    user = _pending_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    row = repository.get_valid_email_code(user["id"])
    submitted = hashlib.sha256(code.strip().encode()).hexdigest()
    # secrets.compare_digest = constant-time comparison (no timing leaks).
    if row is None or not secrets.compare_digest(row["code_hash"], submitted):
        if row is not None:
            repository.bump_code_attempts(user["id"])
            error = "Wrong code. Check the email and try again."
        else:
            error = "Code expired or too many attempts — request a new one."
        return templates.TemplateResponse(
            "verify.html",
            {"request": request, "error": error, "email": user["email"]},
            status_code=400,
        )
    repository.mark_verified(user["id"])
    request.session.clear()
    request.session["user_id"] = user["id"]
    return RedirectResponse("/", status_code=303)


@router.post("/verify/resend")
def resend(request: Request):
    user = _pending_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    _issue_code(user)
    return templates.TemplateResponse(
        "verify.html",
        {"request": request, "error": "A new code was sent.", "email": user["email"]},
    )


def _pending_user(request: Request):
    uid = request.session.get("pending_uid")
    return repository.get_user_by_id(uid) if uid is not None else None


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
