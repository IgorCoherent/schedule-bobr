from collections import defaultdict
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.csrf import generate_csrf_token
from app.auth.deps import get_current_user
from app.calendar_view import (
    MonthWindow,
    admin_create_date,
    build_month_cells,
    calendar_location,
    choose_selected,
    day_heading,
    month_bounds,
    month_title,
    resolve_window,
    shift_month,
    sort_shifts,
    today_minsk,
)
from app.db import get_db
from app.models import Participant, ParticipantRole, Shift, User

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


def _require_user_html(request: Request, db: Session) -> User | RedirectResponse:
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/auth/login", status_code=303)
    return user


def fetch_month_shifts(
    db: Session,
    year: int,
    month: int,
    *,
    role: str,
    participant_id: int | None,
) -> list[Shift]:
    start, end = month_bounds(year, month)
    stmt = (
        select(Shift)
        .options(joinedload(Shift.participant))
        .where(Shift.duty_date >= start, Shift.duty_date < end)
        .order_by(Shift.duty_date)
    )
    if participant_id is not None:
        stmt = stmt.where(Shift.participant_id == participant_id)
    if role in ("cashier", "tech"):
        stmt = stmt.where(Shift.role == ParticipantRole(role))
    return list(db.scalars(stmt).unique().all())


def legend_people(shifts: list[Shift]) -> list[Participant]:
    by_id: dict[int, Participant] = {}
    for shift in shifts:
        by_id[shift.participant.id] = shift.participant
    return sorted(by_id.values(), key=lambda person: person.display_name.casefold())


def assemble_calendar(
    db: Session,
    *,
    path: str,
    month: str | None,
    day: str | None,
    role: str | None,
    view: str | None,
    participant_id: int | None,
    ignore_role: bool,
) -> RedirectResponse | dict[str, Any]:
    today = today_minsk()
    window = resolve_window(
        path,
        month,
        day,
        role,
        view,
        today,
        ignore_role=ignore_role,
    )
    if isinstance(window, RedirectResponse):
        return window
    return _context(db, path, window, participant_id)


def _context(db: Session, path: str, window: MonthWindow, participant_id: int | None) -> dict[str, Any]:
    shifts = fetch_month_shifts(
        db,
        window.year,
        window.month,
        role=window.role,
        participant_id=participant_id,
    )
    by_day: dict[date, list[Shift]] = defaultdict(list)
    for shift in shifts:
        by_day[shift.duty_date].append(shift)
    selected = choose_selected(
        window.year,
        window.month,
        window.today,
        window.explicit_day,
        list(by_day),
    )
    cells = build_month_cells(window.year, window.month, window.today, selected, dict(by_day))
    prev_year, prev_month = shift_month(window.year, window.month, -1)
    next_year, next_month = shift_month(window.year, window.month, 1)
    create_on = admin_create_date(
        window.year,
        window.month,
        window.view,
        window.explicit_day,
        selected,
    )
    return {
        "view": window.view,
        "role": window.role,
        "month_title": month_title(window.year, window.month),
        "month_iso": f"{window.year:04d}-{window.month:02d}",
        "base_path": path,
        "prev_href": calendar_location(path, window.role, window.view, year=prev_year, month=prev_month),
        "next_href": calendar_location(path, window.role, window.view, year=next_year, month=next_month),
        "today_href": calendar_location(
            path,
            window.role,
            window.view,
            year=window.today.year,
            month=window.today.month,
            day=window.today,
        ),
        "href_all": calendar_location(
            path, "all", window.view, year=window.year, month=window.month, day=selected
        ),
        "href_cashier": calendar_location(
            path, "cashier", window.view, year=window.year, month=window.month, day=selected
        ),
        "href_tech": calendar_location(
            path, "tech", window.view, year=window.year, month=window.month, day=selected
        ),
        "href_month": calendar_location(
            path, window.role, "month", year=window.year, month=window.month, day=selected
        ),
        "href_list": calendar_location(
            path, window.role, "list", year=window.year, month=window.month, day=selected
        ),
        "legend": legend_people(shifts) if window.view == "month" else [],
        "cells": cells,
        "selected_label": day_heading(selected),
        "day_shifts": sort_shifts(by_day.get(selected, [])),
        "list_shifts": sorted(
            shifts,
            key=lambda shift: (shift.duty_date, shift.role.value, shift.participant.display_name.casefold()),
        ),
        "create_iso": create_on.isoformat(),
        "show_day_panel": window.view == "month",
    }


@router.get("", response_class=HTMLResponse)
def schedule_all(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    month: Annotated[str | None, Query()] = None,
    day: Annotated[str | None, Query()] = None,
    role: Annotated[str | None, Query()] = None,
    view: Annotated[str | None, Query()] = None,
):
    user_or_redirect = _require_user_html(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user = user_or_redirect
    assembled = assemble_calendar(
        db,
        path="/schedule",
        month=month,
        day=day,
        role=role,
        view=view,
        participant_id=None,
        ignore_role=False,
    )
    if isinstance(assembled, RedirectResponse):
        return assembled
    templates = _templates(request)
    return templates.TemplateResponse(
        request,
        "schedule.html",
        {
            "user": user,
            "csrf_token": generate_csrf_token(request),
            "page": "all",
            "is_admin": user.role.value == "admin",
            "show_role_filter": True,
            "show_admin": False,
            "has_participant": True,
            **assembled,
        },
    )


@router.get("/me", response_class=HTMLResponse)
def schedule_me(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    month: Annotated[str | None, Query()] = None,
    day: Annotated[str | None, Query()] = None,
    role: Annotated[str | None, Query()] = None,
    view: Annotated[str | None, Query()] = None,
):
    user_or_redirect = _require_user_html(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user = user_or_redirect
    base = {
        "user": user,
        "csrf_token": generate_csrf_token(request),
        "page": "me",
        "is_admin": user.role.value == "admin",
        "show_role_filter": False,
        "show_admin": False,
        "has_participant": user.participant_id is not None,
    }
    if user.participant_id is None:
        templates = _templates(request)
        return templates.TemplateResponse(request, "schedule_me.html", base)
    assembled = assemble_calendar(
        db,
        path="/schedule/me",
        month=month,
        day=day,
        role=role,
        view=view,
        participant_id=user.participant_id,
        ignore_role=True,
    )
    if isinstance(assembled, RedirectResponse):
        return assembled
    templates = _templates(request)
    return templates.TemplateResponse(request, "schedule_me.html", {**base, **assembled})
