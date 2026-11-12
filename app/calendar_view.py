import calendar
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi.responses import RedirectResponse

_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_MONTHS_NOM = (
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
)
_MONTHS_GEN = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)
_WEEKDAYS = (
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
)


def today_minsk() -> date:
    return datetime.now(ZoneInfo("Europe/Minsk")).date()


def month_title(year: int, month: int) -> str:
    name = _MONTHS_NOM[month - 1]
    return f"{name[:1].upper()}{name[1:]} {year}"


def day_heading(value: date) -> str:
    weekday = _WEEKDAYS[value.weekday()]
    return f"{weekday}, {value.day} {_MONTHS_GEN[value.month - 1]} {value.year}"


def month_status(today: date, count: int) -> str:
    name = _MONTHS_NOM[today.month - 1]
    return f"Сейчас {name} {today.year} · смен в месяце: {count}"


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


@dataclass
class Cell:
    date: date | None
    in_month: bool
    is_today: bool
    is_selected: bool
    shifts: list[Any]


def _role_rank(shift: Any) -> int:
    role = getattr(shift, "role", "")
    value = getattr(role, "value", role)
    return 0 if value == "cashier" else 1


def _person_name(shift: Any) -> str:
    participant = getattr(shift, "participant", None)
    if participant is None:
        return ""
    return str(getattr(participant, "display_name", ""))


def sort_shifts(shifts: Sequence[Any]) -> list[Any]:
    return sorted(shifts, key=lambda shift: (_role_rank(shift), _person_name(shift).casefold()))


def build_month_cells(
    year: int,
    month: int,
    today: date,
    selected: date,
    shifts_by_day: dict[date, list[Any]],
) -> list[Cell]:
    first = date(year, month, 1)
    lead = first.weekday()
    last_day = calendar.monthrange(year, month)[1]
    cells: list[Cell] = [
        Cell(date=None, in_month=False, is_today=False, is_selected=False, shifts=[])
        for _ in range(lead)
    ]
    for day_num in range(1, last_day + 1):
        current = date(year, month, day_num)
        day_shifts = sort_shifts(list(shifts_by_day.get(current, [])))
        cells.append(
            Cell(
                date=current,
                in_month=True,
                is_today=current == today,
                is_selected=current == selected,
                shifts=day_shifts,
            )
        )
    while len(cells) % 7 != 0:
        cells.append(Cell(date=None, in_month=False, is_today=False, is_selected=False, shifts=[]))
    return cells


def choose_selected(
    year: int,
    month: int,
    today: date,
    explicit_day: date | None,
    shift_days: list[date],
) -> date:
    if explicit_day is not None:
        return explicit_day
    if today.year == year and today.month == month:
        return today
    if shift_days:
        return min(shift_days)
    return date(year, month, 1)


def admin_create_date(
    year: int,
    month: int,
    view: str,
    explicit_day: date | None,
    selected: date,
) -> date:
    if view == "list":
        if explicit_day is not None:
            return explicit_day
        return date(year, month, 1)
    return selected


@dataclass
class MonthWindow:
    year: int
    month: int
    explicit_day: date | None
    role: str
    view: str
    today: date


def calendar_location(
    path: str,
    role: str,
    view: str,
    *,
    year: int | None = None,
    month: int | None = None,
    day: date | None = None,
) -> str:
    parts: list[str] = []
    if year is not None and month is not None:
        parts.append(f"month={year:04d}-{month:02d}")
    if day is not None:
        parts.append(f"day={day.isoformat()}")
    if role in {"cashier", "tech"}:
        parts.append(f"role={role}")
    if view == "list":
        parts.append("view=list")
    if not parts:
        return path
    return f"{path}?{'&'.join(parts)}"


def resolve_window(
    path: str,
    month_raw: str | None,
    day_raw: str | None,
    role_raw: str | None,
    view_raw: str | None,
    today: date,
    *,
    ignore_role: bool,
) -> MonthWindow | RedirectResponse:
    role = "all"
    if not ignore_role and role_raw in {"all", "cashier", "tech"}:
        role = role_raw
    view = "list" if view_raw == "list" else "month"
    if month_raw is None:
        parsed_month: tuple[int, int] | None = (today.year, today.month)
    else:
        match = _MONTH_RE.fullmatch(month_raw)
        if match is None:
            parsed_month = None
        else:
            year = int(match.group(1))
            month = int(match.group(2))
            parsed_month = (year, month) if 1 <= month <= 12 else None
    if parsed_month is None:
        return RedirectResponse(calendar_location(path, role, view), status_code=303)
    year, month = parsed_month
    explicit: date | None = None
    if day_raw:
        try:
            parsed_day = date.fromisoformat(day_raw)
        except ValueError:
            parsed_day = None
        if parsed_day is not None and (parsed_day.year != year or parsed_day.month != month):
            return RedirectResponse(
                calendar_location(
                    path,
                    role,
                    view,
                    year=parsed_day.year,
                    month=parsed_day.month,
                    day=parsed_day,
                ),
                status_code=303,
            )
        explicit = parsed_day
    return MonthWindow(
        year=year,
        month=month,
        explicit_day=explicit,
        role=role,
        view=view,
        today=today,
    )
