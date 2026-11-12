import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth.deps import RequireMemberOrAdmin
from app.db import get_db
from app.models import Participant

router = APIRouter()


@router.get("/avatars/{participant_id}")
def get_avatar(
    participant_id: int,
    user: RequireMemberOrAdmin,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    participant = db.get(Participant, participant_id)
    if participant is None or participant.avatar_webp is None:
        raise HTTPException(status_code=404, detail="Аватар не найден")

    etag_base = participant.avatar_updated_at.isoformat() if participant.avatar_updated_at else ""
    etag = hashlib.md5(f"{participant_id}:{etag_base}".encode()).hexdigest()
    return Response(
        content=participant.avatar_webp,
        media_type="image/webp",
        headers={
            "Cache-Control": "private, max-age=3600",
            "ETag": f'"{etag}"',
        },
    )
