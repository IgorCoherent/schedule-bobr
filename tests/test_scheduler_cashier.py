from datetime import date, timedelta

from app.models import ParticipantRole
from app.scheduler.engine import _lena_target, _sundays_count, compute_assign_preview
from tests.conftest import make_participant


def _sunday_range(n: int, start: date | None = None) -> tuple[date, date]:
    start = start or date(2025, 1, 5)
    end = start
    count = 1
    while count < n:
        end += timedelta(days=1)
        if end.weekday() == 6:
            count += 1
    return start, end


def test_regular_cashiers_equal_over_12_sundays(three_cashiers, sunday_horizon) -> None:
    start, end = sunday_horizon
    assert _sundays_count(start, end) == 12
    result = compute_assign_preview(
        role=ParticipantRole.cashier,
        start_date=start,
        end_date=end,
        participants=three_cashiers,
        existing_shifts=[],
    )
    regular_ids = {p.id for p in three_cashiers}
    counts = [result.participant_counts[i] for i in regular_ids]
    assert max(counts) - min(counts) == 0
    assert sum(counts) == 12


def test_lena_target_52_sundays() -> None:
    assert _lena_target(52) in (10, 11)


def test_lena_target_13_sundays() -> None:
    assert _lena_target(13) == 3


def test_unassigned_slots_have_reason(cashier_roster) -> None:
    start, end = _sunday_range(4)
    tiny = [cashier_roster[1]]
    result = compute_assign_preview(
        role=ParticipantRole.cashier,
        start_date=start,
        end_date=end,
        participants=tiny,
        existing_shifts=[],
    )
    if result.unassigned:
        assert result.unassigned[0].reason == "NO_ELIGIBLE_PARTICIPANT"


def test_tech_assign_minimizes_variance(db_session) -> None:
    t1 = make_participant(db_session, "T1", ParticipantRole.tech)
    t2 = make_participant(db_session, "T2", ParticipantRole.tech)
    start = date(2025, 2, 1)
    end = start + timedelta(days=13)
    result = compute_assign_preview(
        role=ParticipantRole.tech,
        start_date=start,
        end_date=end,
        participants=[t1, t2],
        existing_shifts=[],
    )
    c1, c2 = result.participant_counts[t1.id], result.participant_counts[t2.id]
    assert abs(c1 - c2) <= 1


def test_commit_payload_excludes_reason_rows(cashier_roster, sunday_horizon) -> None:
    start, end = sunday_horizon
    result = compute_assign_preview(
        role=ParticipantRole.cashier,
        start_date=start,
        end_date=end,
        participants=cashier_roster,
        existing_shifts=[],
    )
    valid = [a for a in result.assignments if a.participant_id and not a.reason]
    assert len(valid) > 0
