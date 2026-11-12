from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.passwords import verify_password
from app.models import ParticipantRole, UserRole
from tests.conftest import _extract_csrf, make_participant, make_user


def test_password_change_success(client: TestClient, db_session: Session) -> None:
    p = make_participant(db_session, "Pw", ParticipantRole.cashier)
    make_user(db_session, "pwuser", "Smena2025!", UserRole.member, p)
    r = client.get("/auth/login")
    csrf = _extract_csrf(r.text)
    client.post(
        "/auth/login",
        data={"username": "pwuser", "password": "Smena2025!", "csrf_token": csrf},
    )
    r = client.get("/account")
    csrf = _extract_csrf(r.text)
    r = client.post(
        "/account/password",
        data={
            "current_password": "Smena2025!",
            "new_password": "NewPass2025!",
            "new_password_confirm": "NewPass2025!",
            "csrf_token": csrf,
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    from sqlalchemy import select

    from app.models import User

    u = db_session.scalar(select(User).where(User.username == "pwuser"))
    assert u and verify_password("NewPass2025!", u.password_hash)


def test_password_wrong_current(client: TestClient, db_session: Session) -> None:
    p = make_participant(db_session, "Pw2", ParticipantRole.cashier)
    make_user(db_session, "pwuser2", "Smena2025!", UserRole.member, p)
    r = client.get("/auth/login")
    csrf = _extract_csrf(r.text)
    client.post(
        "/auth/login",
        data={"username": "pwuser2", "password": "Smena2025!", "csrf_token": csrf},
    )
    r = client.get("/account")
    csrf = _extract_csrf(r.text)
    r = client.post(
        "/account/password",
        data={
            "current_password": "wrong",
            "new_password": "NewPass2025!",
            "new_password_confirm": "NewPass2025!",
            "csrf_token": csrf,
        },
    )
    assert r.status_code == 400


def test_password_change_no_csrf(client: TestClient, db_session: Session) -> None:
    p = make_participant(db_session, "Pw3", ParticipantRole.cashier)
    make_user(db_session, "pwuser3", "Smena2025!", UserRole.member, p)
    r = client.get("/auth/login")
    csrf = _extract_csrf(r.text)
    client.post(
        "/auth/login",
        data={"username": "pwuser3", "password": "Smena2025!", "csrf_token": csrf},
    )
    r = client.post(
        "/account/password",
        data={
            "current_password": "Smena2025!",
            "new_password": "NewPass2025!",
            "new_password_confirm": "NewPass2025!",
        },
    )
    assert r.status_code == 403
