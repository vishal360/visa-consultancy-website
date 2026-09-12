"""
Availability engine.

Turns the opening-hours configuration plus existing bookings into the concrete
list of slots a visitor may choose.

Slot times in `Settings.OPENING_HOURS` are wall-clock times in the office
timezone (`TIMEZONE_OFFSET_MINUTES`, IST by default). Dates are stored as naive
calendar dates, but every comparison against "now" -- the minimum lead time, and
whether a slot has already passed -- is done on timezone-aware datetimes so the
arithmetic is correct regardless of where the server itself runs.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from . import db
from .config import settings

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"


def parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value.strip(), DATE_FORMAT).date()
    except (ValueError, AttributeError):
        return None


def parse_time(value: str) -> time | None:
    try:
        return datetime.strptime(value.strip(), TIME_FORMAT).time()
    except (ValueError, AttributeError):
        return None


def now_local() -> datetime:
    """Current time in the office timezone."""
    return datetime.now(settings.tz)


def today() -> date:
    """Today's date *in the office timezone*, not UTC."""
    return now_local().date()


def booking_window() -> tuple[date, date]:
    """Inclusive range of dates the public may book within."""
    start = today()
    return start, start + timedelta(days=settings.booking_window_days)


def earliest_bookable() -> datetime:
    """The cutoff: slots starting before this are too soon to book."""
    return now_local() + timedelta(hours=settings.min_lead_hours)


def is_open(day: date) -> bool:
    if day.isoformat() in settings.HOLIDAYS:
        return False
    return bool(settings.slots_for_weekday(day.weekday()))


def slot_datetime(day: date, hhmm: str) -> datetime:
    """The absolute moment a slot starts, anchored to the office timezone."""
    parsed = parse_time(hhmm) or time(0, 0)
    return datetime.combine(day, parsed, tzinfo=settings.tz)


def slot_is_bookable(day: date, hhmm: str) -> tuple[bool, str, str]:
    """
    Validate one slot against every rule.

    Returns (ok, reason_if_not, code). The code lets callers distinguish a
    *contended* slot -- one that was open but has since been taken or blocked --
    from a slot that was never valid. Contention is a 409, everything else 422.
    """
    window_start, window_end = booking_window()
    if day < window_start:
        return False, "That date is in the past.", "past"
    if day > window_end:
        return (
            False,
            f"We only take bookings up to {settings.booking_window_days} days ahead.",
            "window",
        )
    if day.isoformat() in settings.HOLIDAYS:
        return False, "Our office is closed on that date.", "closed"
    if hhmm not in settings.slots_for_weekday(day.weekday()):
        return False, "That time is outside our opening hours.", "hours"

    full_days, blocked_times = db.blocked_map(day.isoformat(), day.isoformat())
    if day.isoformat() in full_days:
        return False, "Our office is closed on that date.", "blocked"
    if hhmm in blocked_times.get(day.isoformat(), set()):
        return False, "That time is no longer available.", "blocked"

    if slot_datetime(day, hhmm) < earliest_bookable():
        return (
            False,
            f"Please choose a slot at least {settings.min_lead_hours} hours from now.",
            "lead",
        )
    if db.slot_is_taken(day.isoformat(), hhmm):
        return False, "That time slot is already booked.", "taken"
    return True, "", ""


def day_availability(day: date, taken: dict[str, set[str]] | None = None,
                     full_days: set[str] | None = None,
                     blocked_times: dict[str, set[str]] | None = None) -> dict:
    """
    Availability for a single day.

    The lookup maps may be supplied by the caller to avoid N queries when
    building a whole month.
    """
    iso = day.isoformat()
    if taken is None:
        taken = db.taken_slots_between(iso, iso)
    if full_days is None or blocked_times is None:
        full_days, blocked_times = db.blocked_map(iso, iso)

    configured = settings.slots_for_weekday(day.weekday())
    is_holiday = iso in settings.HOLIDAYS or iso in full_days
    cutoff = earliest_bookable()
    taken_today = taken.get(iso, set())
    blocked_today = blocked_times.get(iso, set())

    slots = []
    for hhmm in configured:
        reason = ""
        available = True
        if is_holiday:
            available, reason = False, "closed"
        elif hhmm in taken_today:
            available, reason = False, "booked"
        elif hhmm in blocked_today:
            available, reason = False, "unavailable"
        elif slot_datetime(day, hhmm) < cutoff:
            available, reason = False, "too-soon"
        slots.append(
            {
                "time": hhmm,
                "label": hhmm,
                "available": available,
                "reason": reason,
                "end": _slot_end_label(hhmm),
            }
        )

    open_count = sum(1 for s in slots if s["available"])
    return {
        "date": iso,
        "weekday": day.strftime("%A"),
        "weekday_short": day.strftime("%a"),
        "day_number": day.day,
        "month_label": day.strftime("%B %Y"),
        "pretty": day.strftime("%A %d %B %Y"),
        "is_open": bool(configured) and not is_holiday,
        "is_holiday": is_holiday,
        "slots": slots,
        "open_count": open_count,
        "fully_booked": bool(configured) and not is_holiday and open_count == 0,
        "timezone": settings.timezone_label,
    }


def _slot_end_label(hhmm: str) -> str:
    start = parse_time(hhmm)
    if start is None:
        return ""
    end = (
        datetime.combine(date.today(), start) + timedelta(minutes=settings.slot_minutes)
    ).time()
    return end.strftime(TIME_FORMAT)


def month_availability(year: int, month: int) -> dict:
    """
    Calendar data for one month: every date with a status the UI can colour.
    """
    if not 1 <= month <= 12:
        raise ValueError("Month must be between 1 and 12")
    first = date(year, month, 1)
    next_month = date(year + (month == 12), (month % 12) + 1, 1)
    last = next_month - timedelta(days=1)

    taken = db.taken_slots_between(first.isoformat(), last.isoformat())
    full_days, blocked_times = db.blocked_map(first.isoformat(), last.isoformat())
    window_start, window_end = booking_window()

    days = []
    cursor = first
    while cursor <= last:
        info = day_availability(cursor, taken, full_days, blocked_times)
        in_window = window_start <= cursor <= window_end
        if not in_window:
            status = "out-of-window"
        elif not info["is_open"]:
            status = "closed"
        elif info["open_count"] == 0:
            status = "full"
        elif info["open_count"] <= 2:
            status = "limited"
        else:
            status = "open"
        days.append(
            {
                "date": info["date"],
                "day_number": info["day_number"],
                "weekday": info["weekday_short"],
                "status": status,
                "open_count": info["open_count"],
                "selectable": status in {"open", "limited"},
                "pretty": info["pretty"],
            }
        )
        cursor += timedelta(days=1)

    return {
        "year": year,
        "month": month,
        "month_label": first.strftime("%B %Y"),
        "first_weekday": first.weekday(),  # Monday = 0
        "days": days,
        "prev": _shift_month(year, month, -1),
        "next": _shift_month(year, month, 1),
        "can_go_prev": first > window_start.replace(day=1),
        "can_go_next": next_month <= window_end,
        "timezone": settings.timezone_label,
    }


def _shift_month(year: int, month: int, delta: int) -> dict:
    index = (year * 12 + (month - 1)) + delta
    return {"year": index // 12, "month": index % 12 + 1}


def next_available_days(count: int = 5) -> list[dict]:
    """The soonest days with at least one free slot -- powers the 'quick pick' UI."""
    window_start, window_end = booking_window()
    taken = db.taken_slots_between(window_start.isoformat(), window_end.isoformat())
    full_days, blocked_times = db.blocked_map(
        window_start.isoformat(), window_end.isoformat()
    )
    results: list[dict] = []
    cursor = window_start
    while cursor <= window_end and len(results) < count:
        info = day_availability(cursor, taken, full_days, blocked_times)
        if info["open_count"] > 0:
            results.append(info)
        cursor += timedelta(days=1)
    return results


def opening_hours_summary() -> list[dict]:
    """Human-readable weekly hours for the contact section."""
    names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    summary = []
    for index, name in enumerate(names):
        slots = settings.slots_for_weekday(index)
        if slots:
            label = f"{slots[0]} – {_slot_end_label(slots[-1])}"
        else:
            label = "Closed"
        summary.append({"day": name, "hours": label, "open": bool(slots)})
    return summary
