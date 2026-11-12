from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.auth.csrf import generate_csrf_token, validate_csrf_token
from app.auth.deps import RequireMemberOrAdmin
from app.auth.passwords import hash_password, verify_password
from app.avatars.process import process_image_to_webp
from app.config import get_settings
from app.db import get_db
from app.models import Participant

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


@router.get("", response_class=HTMLResponse)
def account_page(
    request: Request,
    user: RequireMemberOrAdmin,
    db: Annotated[Session, Depends(get_db)],
):
    participant = None
    if user.participant_id:
        participant = db.get(Participant, user.participant_id)
    flash = request.session.pop("flash", None)
    templates = _templates(request)
    return templates.TemplateResponse(
        request,
        "account.html",
        {
            "user": user,
            "participant": participant,
            "csrf_token": generate_csrf_token(request),
            "flash": flash,
            "errors": {},
            "is_admin": user.role.value == "admin",
        },
    )


@router.post("/password", response_class=HTMLResponse)
async def change_password(
    request: Request,
    user: RequireMemberOrAdmin,
    db: Annotated[Session, Depends(get_db)],
    current_password: Annotated[str, Form()] = "",
    new_password: Annotated[str, Form()] = "",
    new_password_confirm: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
):
    validate_csrf_token(request, csrf_token)
    errors: dict[str, str] = {}
    if not verify_password(current_password, user.password_hash):
        errors["current_password"] = "Неверный текущий пароль"
    if len(new_password) < 8:
        errors["new_password"] = "Минимум 8 символов"
    if new_password == current_password:
        errors["new_password"] = "Новый пароль должен отличаться от текущего"
    if new_password != new_password_confirm:
        errors["new_password_confirm"] = "Пароли не совпадают"

    templates = _templates(request)
    participant = db.get(Participant, user.participant_id) if user.participant_id else None

    if errors:
        return templates.TemplateResponse(
            request,
            "account.html",
            {
                "user": user,
                "participant": participant,
                "csrf_token": generate_csrf_token(request),
                "flash": None,
                "errors": errors,
                "is_admin": user.role.value == "admin",
            },
            status_code=400,
        )

    user.password_hash = hash_password(new_password)
    db.add(user)
    db.commit()
    request.session["flash"] = "Пароль изменён"
    return RedirectResponse(url="/account", status_code=303)


@router.post("/avatar")
async def upload_avatar(
    request: Request,
    user: RequireMemberOrAdmin,
    db: Annotated[Session, Depends(get_db)],
    photo: UploadFile = File(...),
    csrf_token: Annotated[str, Form()] = "",
):
    validate_csrf_token(request, csrf_token)
    if user.participant_id is None:
        return Response(status_code=403, content="AVATAR_NO_PARTICIPANT")

    settings = get_settings()
    raw = await photo.read()
    if len(raw) > settings.max_upload_bytes:
        return Response(status_code=400, content="Файл слишком большой")

    participant = db.get(Participant, user.participant_id)
    if participant is None:
        return Response(status_code=403, content="AVATAR_NO_PARTICIPANT")

    try:
        webp = process_image_to_webp(raw)
    except ValueError:
        return Response(status_code=400, content="Недопустимый формат")

    participant.avatar_webp = webp
    participant.avatar_updated_at = datetime.now(UTC)
    db.add(participant)
    db.commit()
    return RedirectResponse(url="/account", status_code=303)


@router.delete("/avatar")
async def delete_avatar(
    request: Request,
    user: RequireMemberOrAdmin,
    db: Annotated[Session, Depends(get_db)],
    csrf_token: Annotated[str, Form(alias="csrf_token")] = "",
):
    from fastapi import HTTPException

    validate_csrf_token(request, csrf_token)
    if user.participant_id is None:
        raise HTTPException(status_code=403, detail="AVATAR_NO_PARTICIPANT")
    participant = db.get(Participant, user.participant_id)
    if participant:
        participant.avatar_webp = None
        participant.avatar_updated_at = None
        db.add(participant)
        db.commit()
    return RedirectResponse(url="/account", status_code=303)
