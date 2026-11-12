from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.csrf import generate_csrf_token
from app.auth.deps import get_current_user
from app.db import get_db
from app.models import ParticipantRole, Shift, User

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


def _require_user_html(request: Request, db: Session) -> User | RedirectResponse:
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/auth/login", status_code=303)
    return user


def _group_by_month(shifts: list[Shift]) -> list[tuple[str, list[Shift]]]:
    groups: dict[str, list[Shift]] = defaultdict(list)
    for s in sorted(shifts, key=lambda x: x.duty_date):
        key = s.duty_date.strftime("%Y — %B")
        groups[key].append(s)
    return list(groups.items())


@router.get("", response_class=HTMLResponse)
def schedule_all(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    role: Annotated[str | None, Query()] = "all",
):
    user_or_redirect = _require_user_html(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user = user_or_redirect

    stmt = select(Shift).options(joinedload(Shift.participant)).order_by(Shift.duty_date)
    if role in ("cashier", "tech"):
        stmt = stmt.where(Shift.role == ParticipantRole(role))
    shifts = list(db.scalars(stmt).all())
    templates = _templates(request)
    return templates.TemplateResponse(
        request,
        "schedule.html",
        {
            "user": user,
            "csrf_token": generate_csrf_token(request),
            "shifts_grouped": _group_by_month(shifts),
            "page": "all",
            "role_filter": role or "all",
            "is_admin": user.role.value == "admin",
        },
    )


@router.get("/me", response_class=HTMLResponse)
def schedule_me(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    user_or_redirect = _require_user_html(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user = user_or_redirect

    shifts: list[Shift] = []
    if user.participant_id:
        stmt = (
            select(Shift)
            .where(Shift.participant_id == user.participant_id)
            .options(joinedload(Shift.participant))
            .order_by(Shift.duty_date)
        )
        shifts = list(db.scalars(stmt).all())

    templates = _templates(request)
    return templates.TemplateResponse(
        request,
        "schedule_me.html",
        {
            "user": user,
            "csrf_token": generate_csrf_token(request),
            "shifts_grouped": _group_by_month(shifts),
            "page": "me",
            "has_participant": user.participant_id is not None,
            "is_admin": user.role.value == "admin",
        },
    )
