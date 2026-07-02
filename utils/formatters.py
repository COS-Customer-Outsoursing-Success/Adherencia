from __future__ import annotations

from datetime import timedelta, datetime
from typing import Any


def td_to_str(value: Any) -> str | None:
    """Convierte timedelta (o None) a string HH:MM:SS."""
    if value is None:
        return None
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        if total < 0:
            return "00:00:00"
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    return str(value)


def dt_to_str(value: Any) -> str | None:
    """Convierte datetime a string ISO."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def safe_pct(numerator: int, denominator: int, decimals: int = 1) -> float:
    """Calcula porcentaje con protección contra división por cero."""
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, decimals)


def hhmmss_to_minutes(value: str | None) -> float:
    """Convierte 'HH:MM:SS' a minutos (float). None/valores inválidos → 0.0."""
    if not value:
        return 0.0
    try:
        h, m, s = value.split(":")
        return int(h) * 60 + int(m) + int(s) / 60
    except (ValueError, AttributeError):
        return 0.0
