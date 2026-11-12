from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.calendar_view import build_month_cells
from app.models import ParticipantRole
from tests.conftest import _extract_csrf, make_participant


def test_november_2026_grid() -> None:
    cells = build_month_cells(2026, 11, date(2026, 11, 12), date(2026, 11, 12), {})
    assert all(not cell.in_month for cell in cells[:6])
    assert cells[6].in_month
    assert cells[6].date == date(2026, 11, 1)
    assert sum(1 for cell in cells if cell.in_month) == 30
    assert len(cells) % 7 == 0
    todays = [cell for cell in cells if cell.is_today]
    assert len(todays) == 1
    assert todays[0].is_selected
    assert todays[0].date == date(2026, 11, 12)


def test_schedule_default_has_month_grid(logged_in_admin: TestClient) -> None:
    response = logged_in_admin.get("/schedule")
    assert response.status_code == 200
    assert "Пн" in response.text
    assert "Вс" in response.text
    assert "calendar-grid" in response.text


def test_invalid_month_redirects(logged_in_admin: TestClient) -> None:
    response = logged_in_admin.get("/schedule?month=foo", follow_redirects=False)
    assert response.status_code == 303
    assert "month=foo" not in response.headers["location"]


def test_create_shift_redirects_to_day(
    logged_in_admin: TestClient,
    db_session: Session,
    admin_user,
) -> None:
    participant = make_participant(db_session, "Новый", ParticipantRole.cashier)
    page = logged_in_admin.get("/admin/shifts")
    csrf = _extract_csrf(page.text)
    response = logged_in_admin.post(
        "/admin/shifts",
        data={
            "csrf_token": csrf,
            "participant_id": str(participant.id),
            "role": "cashier",
            "duty_date": "2025-03-02",
            "note": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/admin/shifts?month=2025-03&day=2025-03-02" in response.headers["location"]
