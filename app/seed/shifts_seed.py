import calendar
import json
from datetime import date
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.db import SessionLocal
from app.models import Participant, ParticipantRole, Shift, User, UserRole

_SEED_NOTE = "[doc]"


def _load_november_doc() -> dict:
    path = Path(__file__).parent / "november_2026_shifts.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _shift_role(participant: Participant, duty_date: date) -> ParticipantRole:
    if participant.role == ParticipantRole.cashier and duty_date.weekday() == calendar.SUNDAY:
        return ParticipantRole.cashier
    return ParticipantRole.tech


def run_shifts_seed() -> None:
    doc = _load_november_doc()
    year = int(doc["year"])
    month = int(doc["month"])
    code_map: dict[str, str] = doc["code_to_username"]
    day_notes: dict[str, str] = doc.get("day_notes", {})
    start = date(year, month, 1)
    end = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)

    with SessionLocal() as db:
        admin = db.scalar(
            select(User).where(User.role == UserRole.admin).order_by(User.id).limit(1)
        )
        if admin is None:
            return

        users = db.scalars(
            select(User).options(joinedload(User.participant)).where(User.participant_id.is_not(None))
        ).all()
        participants = {u.username: u.participant for u in users if u.participant is not None}

        db.execute(
            delete(Shift).where(
                Shift.duty_date >= start,
                Shift.duty_date < end,
                Shift.note.is_not(None),
                Shift.note.like(f"{_SEED_NOTE}%"),
            )
        )
        db.commit()

        for item in doc["assignments"]:
            day = int(item["day"])
            code = str(item["code"])
            username = code_map.get(code)
            if not username:
                continue
            participant = participants.get(username)
            if participant is None:
                continue
            duty_date = date(year, month, day)
            note_parts = [f"{_SEED_NOTE} ноябрь {year}"]
            extra = day_notes.get(str(day))
            if extra:
                note_parts.append(extra)
            shift = Shift(
                participant_id=participant.id,
                role=_shift_role(participant, duty_date),
                duty_date=duty_date,
                note=" — ".join(note_parts),
                created_by=admin.id,
            )
            db.add(shift)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()


def main() -> None:
    run_shifts_seed()


if __name__ == "__main__":
    main()
