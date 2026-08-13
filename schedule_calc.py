"""
Next-run calculator — shared by the GUI display and (later) Task Scheduler.

Given a schedule's day list and time, computes the next occurrence from
the current local clock, handling day-of-week wraparound.
"""

from datetime import datetime, timedelta
from database import DAY_KEYS


def next_run(days_csv: str, hour: int, minute: int,
             now: datetime | None = None) -> datetime | None:
    """Return the next datetime this schedule would fire, or None if
    no days are selected."""
    if not days_csv or not days_csv.strip():
        return None

    now = now or datetime.now()
    selected = set(days_csv.lower().split(","))

    # Python weekday: 0=Monday … 6=Sunday — matches DAY_KEYS order
    for offset in range(8):  # 0=today … 7=next-week-same-day
        candidate = now + timedelta(days=offset)
        day_key = DAY_KEYS[candidate.weekday()]
        if day_key not in selected:
            continue
        run_time = candidate.replace(
            hour=hour, minute=minute, second=0, microsecond=0)
        if run_time > now:
            return run_time
    return None


def format_next_run(days_csv: str, hour: int, minute: int,
                    now: datetime | None = None) -> str:
    """Human-readable next-run string for display."""
    nxt = next_run(days_csv, hour, minute, now)
    if nxt is None:
        return "No days selected"
    now = now or datetime.now()
    delta = nxt - now
    day_name = nxt.strftime("%A")
    time_str = nxt.strftime("%H:%M")

    if delta.days == 0:
        hours_left = delta.seconds // 3600
        mins_left = (delta.seconds % 3600) // 60
        if hours_left > 0:
            return f"Today at {time_str} (in {hours_left}h {mins_left}m)"
        return f"Today at {time_str} (in {mins_left}m)"
    elif delta.days == 1 or (delta.days == 0 and nxt.date() > now.date()):
        return f"Tomorrow at {time_str}"
    else:
        return f"{day_name} at {time_str} ({delta.days} days)"
