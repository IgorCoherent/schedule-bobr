import secrets
from typing import Any

from fastapi import HTTPException, Request, status


def ensure_csrf_in_session(request: Request) -> str:
    session = request.session
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def generate_csrf_token(request: Request) -> str:
    return ensure_csrf_in_session(request)


def validate_csrf_token(request: Request, token: str | None) -> None:
    if not token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing")
    expected = request.session.get("csrf_token")
    if not expected or not secrets.compare_digest(expected, token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def get_csrf_from_form(form: dict[str, Any]) -> str | None:
    raw = form.get("csrf_token")
    if isinstance(raw, str):
        return raw
    return None
