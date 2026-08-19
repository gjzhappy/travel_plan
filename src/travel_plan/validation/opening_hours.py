from datetime import date, datetime, time
from typing import Any

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

def hours_for_day(hours: dict[str, Any], day: date) -> tuple[time, time] | None:
    value = hours.get("special_dates", {}).get(day.isoformat(), "missing")
    if value == "missing": value = hours.get("weekly_hours", {}).get(WEEKDAYS[day.weekday()])
    if value is None: return None
    return (time.fromisoformat(value[0]), time.fromisoformat(value[1]))

def can_visit(hours: dict[str, Any], day: date, arrival: time, duration_min: int) -> bool:
    window = hours_for_day(hours, day)
    if not window: return False
    latest = hours.get("latest_entry_time")
    if latest and arrival > time.fromisoformat(latest): return False
    start = max(arrival, window[0])
    finish = datetime.combine(day, start).timestamp() + duration_min * 60
    return datetime.fromtimestamp(finish).time() <= window[1]

def next_open_time(hours: dict[str, Any], day: date, arrival: time) -> time | None:
    window = hours_for_day(hours, day)
    return max(arrival, window[0]) if window else None

