from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.csrf import generate_csrf_token, validate_csrf_token
from app.auth.deps import RequireMemberOrAdmin
from app.config import get_settings
from app.db import get_db
from app.models import ChatMessage

router = APIRouter()


def _templates(request: Request):
    return request.app.state.templates


@router.get("", response_class=HTMLResponse)
def chat_page(
    request: Request,
    user: RequireMemberOrAdmin,
    db: Annotated[Session, Depends(get_db)],
):
    messages = _fetch_messages(db, limit=50)
    templates = _templates(request)
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "user": user,
            "messages": messages,
            "csrf_token": generate_csrf_token(request),
            "page": "chat",
            "is_admin": user.role.value == "admin",
        },
    )


def _fetch_messages(db: Session, limit: int = 50, before_id: int | None = None) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .options(joinedload(ChatMessage.author))
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    if before_id is not None:
        stmt = stmt.where(ChatMessage.id < before_id)
    rows = list(db.scalars(stmt).all())
    rows.reverse()
    return rows


@router.get("/messages")
def chat_messages_json(
    user: RequireMemberOrAdmin,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query()] = 50,
    before_id: Annotated[int | None, Query()] = None,
) -> JSONResponse:
    messages = _fetch_messages(db, limit=limit, before_id=before_id)
    payload = [
        {
            "id": m.id,
            "text": m.text,
            "created_at": m.created_at.isoformat(),
            "author_name": m.author.display_name,
            "author_participant_id": m.author_participant_id,
        }
        for m in messages
    ]
    return JSONResponse(payload)


@router.post("/messages")
async def post_message(
    request: Request,
    user: RequireMemberOrAdmin,
    db: Annotated[Session, Depends(get_db)],
    text: Annotated[str, Form()] = "",
    csrf_token: Annotated[str, Form()] = "",
):
    validate_csrf_token(request, csrf_token)
    if user.participant_id is None:
        return JSONResponse(
            status_code=403,
            content={"detail": "CHAT_NO_PARTICIPANT"},
        )

    settings = get_settings()
    cleaned = text.strip()
    if not cleaned:
        return RedirectResponse(url="/chat", status_code=303)
    if len(cleaned) > settings.max_text_length:
        cleaned = cleaned[: settings.max_text_length]

    msg = ChatMessage(author_participant_id=user.participant_id, text=cleaned)
    db.add(msg)
    db.commit()

    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({"id": msg.id})
    return RedirectResponse(url="/chat", status_code=303)
