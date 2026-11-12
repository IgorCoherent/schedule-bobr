from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.csrf import generate_csrf_token, validate_csrf_token
from app.auth.deps import RequireAdmin
from app.auth.passwords import hash_password
from app.avatars.process import process_image_to_webp
from app.calendar_view import month_bounds, month_status, today_minsk
from app.config import get_settings
from app.db import get_db
from app.models import AssignPreview, Participant, ParticipantRole, Shift, User, UserRole
from app.routers.schedule import assemble_calendar
from app.scheduler.engine import MIN_GAP_DAYS, compute_assign_preview

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


@router.get("", response_class=HTMLResponse)
def admin_home(
    request: Request,
    user: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
):
    today = today_minsk()
    start, end = month_bounds(today.year, today.month)
    count = db.scalar(
        select(func.count()).select_from(Shift).where(Shift.duty_date >= start, Shift.duty_date < end)
    )
    templates = _templates(request)
    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "user": user,
            "csrf_token": generate_csrf_token(request),
            "is_admin": True,
            "month_status": month_status(today, int(count or 0)),
        },
    )


@router.get("/participants", response_class=HTMLResponse)
def participants_list(
    request: Request,
    user: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
):
    participants = list(db.scalars(select(Participant).order_by(Participant.display_name)).all())
    templates = _templates(request)
    return templates.TemplateResponse(
        request,
        "admin/participants_list.html",
        {
            "user": user,
            "participants": participants,
            "csrf_token": generate_csrf_token(request),
            "is_admin": True,
        },
    )


@router.get("/participants/new", response_class=HTMLResponse)
@router.post("/participants/new", response_class=HTMLResponse)
async def participants_new(
    request: Request,
    user: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
):
    templates = _templates(request)
    if request.method == "GET":
        return templates.TemplateResponse(
            request,
            "admin/participant_form.html",
            {
                "user": user,
                "participant": None,
                "csrf_token": generate_csrf_token(request),
                "errors": {},
                "is_admin": True,
            },
        )

    form = await request.form()
    validate_csrf_token(request, str(form.get("csrf_token", "")))
    display_name = str(form.get("display_name", "")).strip()
    role = str(form.get("role", "cashier"))
    username = str(form.get("username", "")).strip()
    initial_password = str(form.get("initial_password", ""))
    special = form.get("special_cashier_quota") == "on"

    errors: dict[str, str] = {}
    if not display_name:
        errors["display_name"] = "Укажите имя"
    if not username:
        errors["username"] = "Укажите логин"
    if len(initial_password) < 8:
        errors["initial_password"] = "Минимум 8 символов"
    if db.scalar(select(User).where(User.username == username)):
        errors["username"] = "Логин занят"

    if errors:
        return templates.TemplateResponse(
            request,
            "admin/participant_form.html",
            {
                "user": user,
                "participant": None,
                "csrf_token": generate_csrf_token(request),
                "errors": errors,
                "is_admin": True,
            },
            status_code=400,
        )

    p_role = ParticipantRole(role)
    participant = Participant(
        display_name=display_name,
        role=p_role,
        special_cashier_quota=special if p_role == ParticipantRole.cashier else False,
        active=True,
    )
    db.add(participant)
    db.flush()
    member = User(
        username=username,
        password_hash=hash_password(initial_password),
        role=UserRole.member,
        participant_id=participant.id,
    )
    db.add(member)
    db.commit()
    return RedirectResponse(url="/admin/participants", status_code=303)


@router.get("/participants/{participant_id}/edit", response_class=HTMLResponse)
@router.post("/participants/{participant_id}/edit", response_class=HTMLResponse)
async def participants_edit(
    request: Request,
    participant_id: int,
    user: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
):
    participant = db.get(Participant, participant_id)
    if participant is None:
        raise HTTPException(status_code=404)
    templates = _templates(request)

    if request.method == "GET":
        return templates.TemplateResponse(
            request,
            "admin/participant_form.html",
            {
                "user": user,
                "participant": participant,
                "csrf_token": generate_csrf_token(request),
                "errors": {},
                "is_admin": True,
            },
        )

    form = await request.form()
    validate_csrf_token(request, str(form.get("csrf_token", "")))
    participant.display_name = str(form.get("display_name", participant.display_name)).strip()
    participant.role = ParticipantRole(str(form.get("role", participant.role.value)))
    participant.special_cashier_quota = form.get("special_cashier_quota") == "on"
    participant.active = form.get("active") == "on"
    db.add(participant)
    db.commit()
    return RedirectResponse(url="/admin/participants", status_code=303)


@router.post("/participants/{participant_id}/avatar")
async def admin_upload_avatar(
    request: Request,
    participant_id: int,
    user: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    photo: UploadFile = File(...),
    csrf_token: Annotated[str, Form()] = "",
):
    validate_csrf_token(request, csrf_token)
    participant = db.get(Participant, participant_id)
    if participant is None:
        raise HTTPException(status_code=404)

    settings = get_settings()
    raw = await photo.read()
    if len(raw) > settings.max_upload_bytes:
        return Response(status_code=400)

    try:
        webp = process_image_to_webp(raw)
    except ValueError:
        return Response(status_code=400)

    participant.avatar_webp = webp
    participant.avatar_updated_at = datetime.now(UTC)
    db.add(participant)
    db.commit()
    return RedirectResponse(url=f"/admin/participants/{participant_id}/edit", status_code=303)


@router.delete("/participants/{participant_id}/avatar")
async def admin_delete_avatar(
    request: Request,
    participant_id: int,
    user: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    csrf_token: Annotated[str, Form()] = "",
):
    validate_csrf_token(request, csrf_token)
    participant = db.get(Participant, participant_id)
    if participant:
        participant.avatar_webp = None
        participant.avatar_updated_at = None
        db.add(participant)
        db.commit()
    return RedirectResponse(url=f"/admin/participants/{participant_id}/edit", status_code=303)


@router.get("/shifts", response_class=HTMLResponse)
@router.post("/shifts", response_class=HTMLResponse)
@router.delete("/shifts")
async def shifts_admin(
    request: Request,
    user: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    shift_id: Annotated[int | None, Query()] = None,
    month: Annotated[str | None, Query()] = None,
    day: Annotated[str | None, Query()] = None,
    role: Annotated[str | None, Query()] = None,
    view: Annotated[str | None, Query()] = None,
):
    templates = _templates(request)

    if request.method == "DELETE":
        form = await request.form()
        validate_csrf_token(request, str(form.get("csrf_token", "")))
        sid = int(str(form.get("shift_id", shift_id or 0)))
        shift = db.get(Shift, sid)
        if shift:
            deleted = shift.duty_date
            db.delete(shift)
            db.commit()
            return RedirectResponse(
                url=f"/admin/shifts?month={deleted:%Y-%m}&day={deleted.isoformat()}",
                status_code=303,
            )
        return RedirectResponse(url="/admin/shifts", status_code=303)

    if request.method == "POST":
        form = await request.form()
        validate_csrf_token(request, str(form.get("csrf_token", "")))
        participant_id = int(str(form.get("participant_id", 0)))
        shift_role = ParticipantRole(str(form.get("role", "cashier")))
        duty_date = date.fromisoformat(str(form.get("duty_date")))
        note = str(form.get("note", "")).strip() or None

        if shift_role == ParticipantRole.cashier and duty_date.weekday() != 6:
            raise HTTPException(status_code=422, detail="Кассир только по воскресеньям")

        participant = db.get(Participant, participant_id)
        if participant is None:
            raise HTTPException(status_code=400)

        shift = Shift(
            participant_id=participant_id,
            role=shift_role,
            duty_date=duty_date,
            note=note,
            created_by=user.id,
        )
        db.add(shift)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="Конфликт даты") from None
        return RedirectResponse(
            url=f"/admin/shifts?month={duty_date:%Y-%m}&day={duty_date.isoformat()}",
            status_code=303,
        )

    assembled = assemble_calendar(
        db,
        path="/admin/shifts",
        month=month,
        day=day,
        role=role,
        view=view,
        participant_id=None,
        ignore_role=False,
    )
    if isinstance(assembled, RedirectResponse):
        return assembled
    participants = list(db.scalars(select(Participant).where(Participant.active)).all())
    return templates.TemplateResponse(
        request,
        "admin/shifts.html",
        {
            "user": user,
            "participants": participants,
            "csrf_token": generate_csrf_token(request),
            "is_admin": True,
            "show_role_filter": True,
            "show_admin": True,
            **assembled,
        },
    )


@router.post("/shifts/{shift_id}/move")
async def move_shift(
    request: Request,
    shift_id: int,
    user: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    new_date: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
):
    validate_csrf_token(request, csrf_token)
    shift = db.get(Shift, shift_id)
    if shift is None:
        raise HTTPException(status_code=404)

    target = date.fromisoformat(new_date)
    if shift.role == ParticipantRole.cashier and target.weekday() != 6:
        raise HTTPException(status_code=422, detail="Кассир только по воскресеньям")

    other = db.scalar(
        select(Shift).where(
            Shift.participant_id == shift.participant_id,
            Shift.duty_date == target,
            Shift.id != shift_id,
        )
    )
    if other:
        raise HTTPException(status_code=409, detail="Дата занята")

    existing_dates = [
        s.duty_date
        for s in db.scalars(
            select(Shift).where(
                Shift.participant_id == shift.participant_id,
                Shift.id != shift_id,
            )
        ).all()
    ]
    for d in existing_dates:
        if abs((target - d).days) < MIN_GAP_DAYS and target != d:
            raise HTTPException(status_code=422, detail="Нарушен интервал отдыха")

    shift.duty_date = target
    db.add(shift)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Конфликт даты") from None

    return RedirectResponse(
        url=f"/admin/shifts?month={target:%Y-%m}&day={target.isoformat()}",
        status_code=303,
    )


@router.post("/auto-assign/preview")
async def auto_assign_preview(
    request: Request,
    user: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    role: Annotated[str, Form()] = "cashier",
    start_date: Annotated[str, Form()] = "",
    end_date: Annotated[str, Form()] = "",
    replace_existing: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
):
    validate_csrf_token(request, csrf_token)
    p_role = ParticipantRole(role)
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    replace = replace_existing.lower() in ("true", "on", "1", "yes")

    participants = list(db.scalars(select(Participant)).all())
    existing = list(
        db.scalars(
            select(Shift).where(Shift.duty_date >= start, Shift.duty_date <= end)
        ).all()
    )

    result = compute_assign_preview(
        role=p_role,
        start_date=start,
        end_date=end,
        participants=participants,
        existing_shifts=existing,
        replace_existing=replace,
    )

    preview = AssignPreview(
        payload=result.payload,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )
    db.add(preview)
    db.commit()
    db.refresh(preview)

    templates = _templates(request)
    return templates.TemplateResponse(
        request,
        "admin/auto_assign_preview.html",
        {
            "user": user,
            "preview_id": preview.id,
            "result": result,
            "csrf_token": generate_csrf_token(request),
            "is_admin": True,
        },
    )


@router.post("/auto-assign/commit")
async def auto_assign_commit(
    request: Request,
    user: RequireAdmin,
    db: Annotated[Session, Depends(get_db)],
    preview_id: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
):
    validate_csrf_token(request, csrf_token)
    try:
        pid = UUID(preview_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неверный preview_id") from exc

    preview = db.get(AssignPreview, pid)
    if preview is None:
        raise HTTPException(status_code=404)
    if preview.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Preview истёк")

    payload = preview.payload
    created = 0
    try:
        for item in payload.get("assignments", []):
            if item.get("reason"):
                continue
            if not item.get("is_new", True):
                continue
            participant_id = item.get("participant_id")
            if participant_id is None:
                continue
            duty_date = date.fromisoformat(item["duty_date"])
            role = ParticipantRole(item["role"])
            shift = Shift(
                participant_id=participant_id,
                role=role,
                duty_date=duty_date,
                created_by=user.id,
            )
            db.add(shift)
            created += 1
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ошибка сохранения") from None

    return RedirectResponse(url="/admin/shifts", status_code=303)
