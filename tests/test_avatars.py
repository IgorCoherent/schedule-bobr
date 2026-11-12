import io

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.models import Participant, ParticipantRole, Shift, UserRole
from tests.conftest import _extract_csrf, make_participant, make_user


def _png_bytes() -> bytes:
    img = Image.new("RGB", (64, 64), color=(120, 80, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_upload_avatar_and_serve(client: TestClient, db_session: Session) -> None:
    p = make_participant(db_session, "Av", ParticipantRole.cashier)
    make_user(db_session, "avuser", "Smena2025!", UserRole.member, p)
    r = client.get("/auth/login")
    csrf = _extract_csrf(r.text)
    client.post(
        "/auth/login",
        data={"username": "avuser", "password": "Smena2025!", "csrf_token": csrf},
    )
    r = client.post(
        "/account/avatar",
        data={"csrf_token": csrf},
        files={"photo": ("t.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 303
    part = db_session.get(Participant, p.id)
    assert part and part.avatar_webp
    r = client.get(f"/avatars/{p.id}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/webp")


def test_schedule_shows_avatar_img(client: TestClient, db_session: Session, admin_user) -> None:
    p = make_participant(db_session, "Av2", ParticipantRole.cashier)
    make_user(db_session, "av2", "Smena2025!", UserRole.member, p)
    from app.avatars.process import process_image_to_webp

    p.avatar_webp = process_image_to_webp(_png_bytes())
    db_session.add(p)
    from datetime import date

    shift = Shift(
        participant_id=p.id,
        role=ParticipantRole.cashier,
        duty_date=date(2025, 4, 6),
        created_by=admin_user.id,
    )
    db_session.add(shift)
    db_session.commit()
    r = client.get("/auth/login")
    csrf = _extract_csrf(r.text)
    client.post(
        "/auth/login",
        data={"username": "av2", "password": "Smena2025!", "csrf_token": csrf},
    )
    r = client.get("/schedule?month=2025-04&day=2025-04-06")
    assert f"/avatars/{p.id}" in r.text


def test_member_no_participant_avatar_403(client: TestClient, admin_user) -> None:
    r = client.get("/auth/login")
    csrf = _extract_csrf(r.text)
    client.post(
        "/auth/login",
        data={"username": "tamara", "password": "Tamara2025!", "csrf_token": csrf},
    )
    r = client.post(
        "/account/avatar",
        data={"csrf_token": csrf},
        files={"photo": ("t.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 403


def test_bad_upload_400(client: TestClient, db_session: Session) -> None:
    p = make_participant(db_session, "Av3", ParticipantRole.cashier)
    make_user(db_session, "av3", "Smena2025!", UserRole.member, p)
    r = client.get("/auth/login")
    csrf = _extract_csrf(r.text)
    client.post(
        "/auth/login",
        data={"username": "av3", "password": "Smena2025!", "csrf_token": csrf},
    )
    r = client.post(
        "/account/avatar",
        data={"csrf_token": csrf},
        files={"photo": ("t.txt", b"not-image", "text/plain")},
    )
    assert r.status_code == 400
    part = db_session.get(Participant, p.id)
    assert part and part.avatar_webp is None


def test_admin_participant_avatar(logged_in_admin: TestClient, db_session: Session) -> None:
    p = make_participant(db_session, "Av4", ParticipantRole.tech)
    r = logged_in_admin.get("/admin/shifts")
    csrf = _extract_csrf(r.text)
    r = logged_in_admin.post(
        f"/admin/participants/{p.id}/avatar",
        data={"csrf_token": csrf},
        files={"photo": ("t.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 303
    part = db_session.get(Participant, p.id)
    assert part and part.avatar_webp
