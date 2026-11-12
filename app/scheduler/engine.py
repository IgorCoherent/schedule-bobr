from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from app.models import Participant, ParticipantRole, Shift

REASON_NO_ELIGIBLE = "NO_ELIGIBLE_PARTICIPANT"
MIN_GAP_DAYS = 3


@dataclass
class SlotAssignment:
    duty_date: date
    role: ParticipantRole
    participant_id: int | None = None
    reason: str | None = None
    is_new: bool = True


@dataclass
class PreviewResult:
    assignments: list[SlotAssignment] = field(default_factory=list)
    unassigned: list[SlotAssignment] = field(default_factory=list)
    participant_counts: dict[int, int] = field(default_factory=dict)
    lena_adjacent_pairs: int = 0
    payload: dict[str, Any] = field(default_factory=dict)


def _dates_in_horizon(start: date, end: date, sundays_only: bool) -> list[date]:
    out: list[date] = []
    d = start
    while d <= end:
        if not sundays_only or d.weekday() == 6:
            out.append(d)
        d += timedelta(days=1)
    return out


def _sundays_count(start: date, end: date) -> int:
    return len(_dates_in_horizon(start, end, sundays_only=True))


def _lena_target(sundays_in_horizon: int) -> int:
    if sundays_in_horizon >= 52:
        return max(10, min(11, round(10.5)))
    if sundays_in_horizon == 0:
        return 0
    raw = round(10.5 * sundays_in_horizon / 52)
    return max(0, min(sundays_in_horizon, raw))


def _regular_targets(participants: list[Participant], sundays_in_horizon: int) -> dict[int, int]:
    regular = [p for p in participants if not p.special_cashier_quota]
    n_regular = len(regular)
    if n_regular == 0:
        return {}
    base = sundays_in_horizon // n_regular
    remainder = sundays_in_horizon - base * n_regular
    regular.sort(key=lambda p: p.id)
    targets: dict[int, int] = {}
    for i, p in enumerate(regular):
        targets[p.id] = base + (1 if i < remainder else 0)
    return targets


def _rest_ok(duty_dates: list[date], new_date: date) -> bool:
    for existing in duty_dates:
        if abs((new_date - existing).days) < MIN_GAP_DAYS and new_date != existing:
            if (new_date - existing).days != 0 and abs((new_date - existing).days) < MIN_GAP_DAYS:
                return False
        if existing != new_date and abs((new_date - existing).days) < MIN_GAP_DAYS:
            return False
    return True


def _rest_ok_strict(duty_dates: list[date], new_date: date) -> bool:
    for existing in duty_dates:
        if existing == new_date:
            return False
        gap = abs((new_date - existing).days)
        if gap < MIN_GAP_DAYS:
            return False
    return True


def _participant_dates(
    participant_id: int,
    existing: list[Shift],
    assigned: list[tuple[date, int]],
) -> list[date]:
    dates = [s.duty_date for s in existing if s.participant_id == participant_id]
    dates.extend(d for d, pid in assigned if pid == participant_id)
    return sorted(set(dates))


def _count_adjacent_sunday_pairs(dates: list[date]) -> int:
    sundays = sorted(d for d in dates if d.weekday() == 6)
    pairs = 0
    for i in range(len(sundays) - 1):
        if (sundays[i + 1] - sundays[i]).days == 7:
            pairs += 1
    return pairs


def compute_assign_preview(
    *,
    role: ParticipantRole,
    start_date: date,
    end_date: date,
    participants: list[Participant],
    existing_shifts: list[Shift],
    replace_existing: bool = False,
) -> PreviewResult:
    active = [p for p in participants if p.active and p.role == role]
    role_existing = [s for s in existing_shifts if s.role == role and start_date <= s.duty_date <= end_date]

    occupied: dict[tuple[date, ParticipantRole], Shift] = {}
    for s in role_existing:
        if not replace_existing:
            occupied[(s.duty_date, s.role)] = s

    sundays_only = role == ParticipantRole.cashier
    empty_slots = []
    for d in _dates_in_horizon(start_date, end_date, sundays_only):
        if (d, role) not in occupied:
            empty_slots.append(d)
    empty_slots.sort()

    counts: dict[int, int] = {p.id: 0 for p in active}
    for s in role_existing:
        if s.participant_id in counts:
            counts[s.participant_id] += 1

    targets: dict[int, int] = {}
    if role == ParticipantRole.cashier:
        sc = _sundays_count(start_date, end_date)
        targets = _regular_targets(active, sc)
        for p in active:
            if p.special_cashier_quota:
                targets[p.id] = _lena_target(sc)

    assigned_new: list[tuple[date, int]] = []
    assignments: list[SlotAssignment] = []
    unassigned: list[SlotAssignment] = []

    for slot_date in empty_slots:
        eligible: list[tuple[int, int]] = []
        for p in active:
            dates = _participant_dates(p.id, role_existing, assigned_new)
            if not _rest_ok_strict(dates, slot_date):
                continue
            global_conflict = any(
                s.participant_id == p.id and s.duty_date == slot_date
                for s in existing_shifts
            ) or any(pid == p.id and d == slot_date for d, pid in assigned_new)
            if global_conflict:
                continue
            tgt = targets.get(p.id)
            cur = counts.get(p.id, 0)
            if tgt is not None and cur >= tgt:
                continue
            eligible.append((counts.get(p.id, 0), p.id))

        if not eligible:
            ua = SlotAssignment(duty_date=slot_date, role=role, reason=REASON_NO_ELIGIBLE)
            unassigned.append(ua)
            assignments.append(ua)
            continue

        eligible.sort(key=lambda x: (x[0], x[1]))
        _, pick_id = eligible[0]
        counts[pick_id] = counts.get(pick_id, 0) + 1
        assigned_new.append((slot_date, pick_id))
        assignments.append(
            SlotAssignment(duty_date=slot_date, role=role, participant_id=pick_id, is_new=True)
        )

    _local_swap_pass(
        role, active, role_existing, existing_shifts, assignments, counts, targets, max_iter=3
    )

    unassigned = [a for a in assignments if a.participant_id is None and a.reason]

    lena_id = next((p.id for p in active if p.special_cashier_quota), None)
    lena_pairs = 0
    if lena_id is not None:
        all_dates = _participant_dates(lena_id, role_existing, assigned_new)
        for a in assignments:
            if a.participant_id == lena_id and a.is_new:
                all_dates.append(a.duty_date)
        lena_pairs = _count_adjacent_sunday_pairs(all_dates)

    new_shifts = [
        {
            "duty_date": a.duty_date.isoformat(),
            "role": a.role.value,
            "participant_id": a.participant_id,
            "reason": a.reason,
            "is_new": a.is_new,
        }
        for a in assignments
    ]

    payload = {
        "role": role.value,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "replace_existing": replace_existing,
        "assignments": new_shifts,
        "participant_counts": {str(k): v for k, v in counts.items()},
        "lena_adjacent_pairs": lena_pairs,
    }

    return PreviewResult(
        assignments=assignments,
        unassigned=unassigned,
        participant_counts=counts,
        lena_adjacent_pairs=lena_pairs,
        payload=payload,
    )


def _local_swap_pass(
    role: ParticipantRole,
    active: list[Participant],
    role_existing: list[Shift],
    all_existing: list[Shift],
    assignments: list[SlotAssignment],
    counts: dict[int, int],
    targets: dict[int, int],
    max_iter: int,
) -> None:
    regular = [p for p in active if not getattr(p, "special_cashier_quota", False)]
    if len(regular) < 2:
        return

    for _ in range(max_iter):
        improved = False
        new_assignments = [a for a in assignments if a.participant_id is not None and a.is_new]
        for i, a1 in enumerate(new_assignments):
            for a2 in new_assignments[i + 1 :]:
                if a1.participant_id == a2.participant_id:
                    continue
                p1, p2 = a1.participant_id, a2.participant_id
                if p1 is None or p2 is None:
                    continue
                c1, c2 = counts.get(p1, 0), counts.get(p2, 0)
                if abs(c1 - c2) <= 1:
                    continue
                if not _swap_feasible(a1, a2, p1, p2, role_existing, all_existing, assignments):
                    continue
                a1.participant_id, a2.participant_id = p2, p1
                counts[p1] = counts.get(p1, 0) - 1
                counts[p2] = counts.get(p2, 0) + 1
                improved = True
        if not improved:
            break


def _swap_feasible(
    a1: SlotAssignment,
    a2: SlotAssignment,
    p1: int,
    p2: int,
    role_existing: list[Shift],
    all_existing: list[Shift],
    assignments: list[SlotAssignment],
) -> bool:
    def dates_for(pid: int, exclude: SlotAssignment) -> list[date]:
        dts = [s.duty_date for s in role_existing if s.participant_id == pid]
        for a in assignments:
            if a is exclude or a.participant_id is None:
                continue
            if a.participant_id == pid:
                dts.append(a.duty_date)
        return dts

    d1 = dates_for(p2, a1) + [a2.duty_date]
    d2 = dates_for(p1, a2) + [a1.duty_date]
    if not _rest_ok_strict(d1, a1.duty_date) or not _rest_ok_strict(d2, a2.duty_date):
        return False
    for s in all_existing:
        if s.participant_id == p2 and s.duty_date == a1.duty_date:
            return False
        if s.participant_id == p1 and s.duty_date == a2.duty_date:
            return False
    return True


def tech_assign_preview(
    start_date: date,
    end_date: date,
    participants: list[Participant],
    existing_shifts: list[Shift],
    replace_existing: bool = False,
) -> PreviewResult:
    return compute_assign_preview(
        role=ParticipantRole.tech,
        start_date=start_date,
        end_date=end_date,
        participants=participants,
        existing_shifts=existing_shifts,
        replace_existing=replace_existing,
    )
