from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ParticipantRole, Shift, UserRole
from tests.conftest import _extract_csrf, make_participant, make_user


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_admin_login_and_admin_page(client: TestClient, admin_user) -> None:
    r = client.get("/auth/login")
    csrf = _extract_csrf(r.text)
    r = client.post(
        "/auth/login",
        data={"username": "tamara", "password": "Tamara2025!", "csrf_token": csrf},
    )
    assert r.status_code == 303
    r = client.get("/admin")
    assert r.status_code == 200


def test_schedule_me_only_own_shifts(client: TestClient, db_session: Session) -> None:
    p1 = make_participant(db_session, "U1", ParticipantRole.cashier)
    p2 = make_participant(db_session, "U2", ParticipantRole.cashier)
    make_user(db_session, "u1", "Smena2025!", UserRole.member, p1)
    admin = make_user(db_session, "adm", "Tamara2025!", UserRole.admin)
    shift1 = Shift(
        participant_id=p1.id,
        role=ParticipantRole.cashier,
        duty_date=date(2025, 3, 2),
        created_by=admin.id,
    )
    shift2 = Shift(
        participant_id=p2.id,
        role=ParticipantRole.cashier,
        duty_date=date(2025, 3, 9),
        created_by=admin.id,
    )
    db_session.add_all([shift1, shift2])
    db_session.commit()

    r = client.get("/auth/login")
    csrf = _extract_csrf(r.text)
    client.post(
        "/auth/login",
        data={"username": "u1", "password": "Smena2025!", "csrf_token": csrf},
    )
    r = client.get("/schedule/me")
    assert r.status_code == 200
    assert "U1" in r.text or "03.02.2025" in r.text
    assert "U2" not in r.text
