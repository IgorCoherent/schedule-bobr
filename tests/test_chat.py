from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ParticipantRole, UserRole
from tests.conftest import _extract_csrf, make_participant, make_user


def test_chat_post_and_list_chronological(client: TestClient, db_session: Session) -> None:
    p = make_participant(db_session, "Ch", ParticipantRole.tech)
    make_user(db_session, "chuser", "Smena2025!", UserRole.member, p)
    r = client.get("/auth/login")
    csrf = _extract_csrf(r.text)
    client.post(
        "/auth/login",
        data={"username": "chuser", "password": "Smena2025!", "csrf_token": csrf},
    )
    client.post(
        "/chat/messages",
        data={"text": "Первое", "csrf_token": csrf},
        headers={"accept": "application/json"},
    )
    client.post(
        "/chat/messages",
        data={"text": "Второе", "csrf_token": csrf},
        headers={"accept": "application/json"},
    )
    msgs = client.get("/chat/messages").json()
    assert len(msgs) >= 2
    assert msgs[0]["text"] == "Первое"
    assert msgs[-1]["text"] == "Второе"


def test_chat_without_participant_403(client: TestClient, admin_user) -> None:
    r = client.get("/auth/login")
    csrf = _extract_csrf(r.text)
    client.post(
        "/auth/login",
        data={"username": "tamara", "password": "Tamara2025!", "csrf_token": csrf},
    )
    r = client.post(
        "/chat/messages",
        data={"text": "Hi", "csrf_token": csrf},
        headers={"accept": "application/json"},
    )
    assert r.status_code == 403
