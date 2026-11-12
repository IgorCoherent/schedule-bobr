import os
from collections.abc import Generator
from datetime import date, timedelta

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/schedule_bobr_test",
    ),
)
os.environ["TEST_DATABASE_URL"] = os.environ["DATABASE_URL"]

from app.auth.passwords import hash_password  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Participant, ParticipantRole, User, UserRole  # noqa: E402


def _run_migrations(url: str) -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def engine():
    url = os.environ["DATABASE_URL"]
    eng = create_engine(url, pool_pre_ping=True)
    with eng.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    _run_migrations(url)
    return eng


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_user(
    db: Session,
    username: str,
    password: str,
    role: UserRole,
    participant: Participant | None = None,
) -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=role,
        participant_id=participant.id if participant else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_participant(
    db: Session,
    name: str,
    role: ParticipantRole,
    *,
    special: bool = False,
) -> Participant:
    p = Participant(
        display_name=name,
        role=role,
        special_cashier_quota=special,
        active=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@pytest.fixture
def admin_user(db_session: Session) -> User:
    return make_user(db_session, "tamara", "Tamara2025!", UserRole.admin)


@pytest.fixture
def logged_in_admin(client: TestClient, admin_user: User) -> TestClient:
    r = client.get("/auth/login")
    csrf = _extract_csrf(r.text)
    client.post(
        "/auth/login",
        data={"username": "tamara", "password": "Tamara2025!", "csrf_token": csrf},
        follow_redirects=False,
    )
    return client


def _extract_csrf(html: str) -> str:
    import re

    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, "csrf token not found"
    return m.group(1)


@pytest.fixture
def sunday_horizon() -> tuple[date, date]:
    start = date(2025, 1, 5)
    end = start + timedelta(weeks=11)
    while end.weekday() != 6:
        end -= timedelta(days=1)
    return start, end


@pytest.fixture
def three_cashiers(db_session: Session) -> list[Participant]:
    return [
        make_participant(db_session, "A", ParticipantRole.cashier),
        make_participant(db_session, "B", ParticipantRole.cashier),
        make_participant(db_session, "C", ParticipantRole.cashier),
    ]


@pytest.fixture
def cashier_roster(db_session: Session) -> list[Participant]:
    return [
        make_participant(db_session, "Лена", ParticipantRole.cashier, special=True),
        make_participant(db_session, "Н1", ParticipantRole.cashier),
        make_participant(db_session, "Н2", ParticipantRole.cashier),
        make_participant(db_session, "Н3", ParticipantRole.cashier),
    ]
