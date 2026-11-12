from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ParticipantRole, Shift, UserRole
from tests.conftest import _extract_csrf, make_participant, make_user


def test_schedule_role_filter(client: TestClient, db_session: Session) -> None:
    admin = make_user(db_session, "adm2", "Tamara2025!", UserRole.admin)
    pc = make_participant(db_session, "C", ParticipantRole.cashier)
    pt = make_participant(db_session, "T", ParticipantRole.tech)
    db_session.add_all(
        [
            Shift(
                participant_id=pc.id,
                role=ParticipantRole.cashier,
                duty_date=date(2025, 2, 2),
                created_by=admin.id,
            ),
            Shift(
                participant_id=pt.id,
                role=ParticipantRole.tech,
                duty_date=date(2025, 2, 3),
                created_by=admin.id,
            ),
        ]
    )
    db_session.commit()
    make_user(db_session, "m1", "Smena2025!", UserRole.member, pc)
    r = client.get("/auth/login")
    csrf = _extract_csrf(r.text)
    client.post(
        "/auth/login",
        data={"username": "m1", "password": "Smena2025!", "csrf_token": csrf},
    )
    r = client.get("/schedule?month=2025-02&day=2025-02-02&role=cashier")
    assert r.status_code == 200
    assert 'aria-label="C, Кассир"' in r.text
    assert 'aria-label="T, Техничка"' not in r.text


def test_move_shift_conflict_409(logged_in_admin: TestClient, db_session: Session, admin_user) -> None:
    p = make_participant(db_session, "P", ParticipantRole.cashier)
    s1 = Shift(
        participant_id=p.id,
        role=ParticipantRole.cashier,
        duty_date=date(2025, 3, 2),
        created_by=admin_user.id,
    )
    s2 = Shift(
        participant_id=p.id,
        role=ParticipantRole.cashier,
        duty_date=date(2025, 3, 16),
        created_by=admin_user.id,
    )
    db_session.add_all([s1, s2])
    db_session.commit()
    r = logged_in_admin.get("/admin/shifts")
    csrf = _extract_csrf(r.text)
    r = logged_in_admin.post(
        f"/admin/shifts/{s1.id}/move",
        data={"new_date": "2025-03-16", "csrf_token": csrf},
    )
    assert r.status_code == 409


def test_cashier_move_non_sunday_422(
    logged_in_admin: TestClient, db_session: Session, admin_user
) -> None:
    p = make_participant(db_session, "P2", ParticipantRole.cashier)
    s = Shift(
        participant_id=p.id,
        role=ParticipantRole.cashier,
        duty_date=date(2025, 3, 2),
        created_by=admin_user.id,
    )
    db_session.add(s)
    db_session.commit()
    r = logged_in_admin.get("/admin/shifts")
    csrf = _extract_csrf(r.text)
    r = logged_in_admin.post(
        f"/admin/shifts/{s.id}/move",
        data={"new_date": "2025-03-03", "csrf_token": csrf},
    )
    assert r.status_code == 422
