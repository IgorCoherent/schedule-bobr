from datetime import date

from app.models import ParticipantRole, Shift, UserRole
from app.scheduler.engine import _rest_ok_strict, compute_assign_preview
from tests.conftest import make_user


def test_rest_gap_less_than_three_rejected() -> None:
    assert not _rest_ok_strict([date(2025, 1, 5)], date(2025, 1, 7))


def test_rest_gap_three_ok() -> None:
    assert _rest_ok_strict([date(2025, 1, 5)], date(2025, 1, 8))


def test_scheduler_respects_existing_shift_rest(db_session, three_cashiers) -> None:
    admin = make_user(db_session, "a", "Tamara2025!", UserRole.admin)
    p = three_cashiers[0]
    existing = [
        Shift(
            participant_id=p.id,
            role=ParticipantRole.cashier,
            duty_date=date(2025, 1, 5),
            created_by=admin.id,
        )
    ]
    db_session.add(existing[0])
    db_session.commit()

    result = compute_assign_preview(
        role=ParticipantRole.cashier,
        start_date=date(2025, 1, 5),
        end_date=date(2025, 1, 19),
        participants=three_cashiers,
        existing_shifts=existing,
    )
    for a in result.assignments:
        if a.participant_id == p.id and a.duty_date == date(2025, 1, 12):
            raise AssertionError("assigned too soon after existing")
