from __future__ import annotations

from datetime import timedelta

import durationpy


def parse_duration(value: str | int | float | timedelta | None) -> timedelta:
    if value is None:
        return timedelta()
    if isinstance(value, timedelta):
        return value
    if isinstance(value, (int, float)):
        return timedelta(seconds=float(value))
    parsed = durationpy.from_str(value)
    if isinstance(parsed, timedelta):
        return parsed
    return timedelta(seconds=parsed)


def format_duration(value: timedelta) -> str:
    seconds = value.total_seconds()
    if seconds == 0:
        return "0s"
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds.is_integer():
        total = int(seconds)
        minutes, rem = divmod(total, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h{minutes}m{rem}s"
        if minutes:
            return f"{minutes}m{rem}s"
        return f"{rem}s"
    return f"{seconds:.3f}s".rstrip("0").rstrip(".") + "s"
