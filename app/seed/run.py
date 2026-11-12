import json
from pathlib import Path

from sqlalchemy import select

from app.auth.passwords import hash_password
from app.config import get_settings
from app.db import SessionLocal
from app.models import Participant, ParticipantRole, User, UserRole


def load_seed_rows() -> list[dict]:
    path = Path(__file__).parent / "participants_seed.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def run_seed() -> None:
    settings = get_settings()
    rows = load_seed_rows()
    with SessionLocal() as db:
        for row in rows:
            username = row["username"]
            existing = db.scalar(select(User).where(User.username == username))
            if existing:
                continue
            user_role = UserRole(row["user_role"])
            participant_id = None
            if user_role == UserRole.member:
                p_role = ParticipantRole(row["role"])
                participant = Participant(
                    display_name=row["display_name"],
                    role=p_role,
                    special_cashier_quota=bool(row.get("special_cashier_quota", False)),
                    active=bool(row.get("active", True)),
                )
                db.add(participant)
                db.flush()
                participant_id = participant.id
            user = User(
                username=username,
                password_hash=hash_password(row["initial_password"]),
                role=user_role,
                participant_id=participant_id,
            )
            db.add(user)
        db.commit()

        if settings.bootstrap_on_start:
            any_user = db.scalar(select(User).limit(1))
            if any_user is None:
                admin = User(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                    role=UserRole.admin,
                    participant_id=None,
                )
                db.add(admin)
                db.commit()


def main() -> None:
    run_seed()


if __name__ == "__main__":
    main()
