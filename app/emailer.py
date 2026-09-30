"""Outgoing email via SMTP.

Configured entirely through environment variables (see .env.example) so it
works with any provider's free tier — Brevo, Resend, Gmail app password, etc.

Dev mode: when SMTP_HOST is not set, the email is printed to the console
instead of sent, so the whole verification flow works locally with no account.
"""

import os
import smtplib
from email.message import EmailMessage


def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True if handed to the SMTP server."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        print(f"[DEV email] To: {to}\nSubject: {subject}\n{body}\n", flush=True)
        return True

    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("SMTP_FROM", user)

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        if port == 465:  # implicit TLS
            with smtplib.SMTP_SSL(host, port, timeout=15) as smtp:
                smtp.login(user, password)
                smtp.send_message(msg)
        else:  # STARTTLS (587, the usual default)
            with smtplib.SMTP(host, port, timeout=15) as smtp:
                smtp.starttls()
                smtp.login(user, password)
                smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as e:
        print(f"[email error] could not send to {to}: {e}", flush=True)
        return False


def send_verification_code(to: str, code: str) -> bool:
    return send_email(
        to,
        "Your Recipes verification code",
        f"Your verification code is: {code}\n\n"
        "It expires in 15 minutes. If you didn't request this, ignore this email.",
    )
