from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.csrf import generate_csrf_token, validate_csrf_token
from app.auth.deps import get_current_user
from app.auth.passwords import verify_password
from app.db import get_db
from app.models import User

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


@router.get("/login", response_class=HTMLResponse)
def login_get(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url="/schedule", status_code=303)
    csrf_token = generate_csrf_token(request)
    templates = _templates(request)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"csrf_token": csrf_token, "error": None},
    )


@router.post("/login")
async def login_post(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    username: Annotated[str, Form()] = "",
    password: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
):
    validate_csrf_token(request, csrf_token)
    user = db.scalar(select(User).where(User.username == username.strip()))
    templates = _templates(request)
    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "csrf_token": generate_csrf_token(request),
                "error": "Неверный логин или пароль",
            },
            status_code=400,
        )
    request.session["user_id"] = user.id
    return RedirectResponse(url="/schedule", status_code=303)


@router.post("/logout")
async def logout_post(
    request: Request,
    csrf_token: Annotated[str, Form()] = "",
):
    validate_csrf_token(request, csrf_token)
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=303)
