from __future__ import annotations

from datetime import date, timedelta

# Fecha más antigua con histórico cargado (inicio del backfill inicial). No hay
# datos antes de esto, así que ninguna fecha resuelta debe quedar por debajo.
MIN_AVAILABLE_DATE = "2026-08-01"


def default_range() -> tuple[str, str]:
    """Rango por defecto cuando el usuario no elige fechas.

    Los primeros 4 días del mes casi no tienen datos del mes en curso, así que
    se muestra el mes anterior completo. Desde el día 5 en adelante se muestra
    el mes actual, de su día 1 a hoy.
    """
    today = date.today()
    if today.day <= 4:
        last_day_prev = today.replace(day=1) - timedelta(days=1)
        first_day_prev = last_day_prev.replace(day=1)
        return first_day_prev.isoformat(), last_day_prev.isoformat()
    return today.replace(day=1).isoformat(), today.isoformat()


def resolve_date_range(filters: dict) -> tuple[str, str]:
    """Devuelve (fecha_inicio, fecha_fin) en formato ISO a partir de los filtros
    de la request, o el rango por defecto si no se especificó ninguna fecha."""
    inicio = (filters or {}).get("fecha_inicio") or ""
    fin = (filters or {}).get("fecha_fin") or ""
    if not inicio and not fin:
        return default_range()
    inicio, fin = inicio or fin, fin or inicio
    inicio, fin = (fin, inicio) if inicio > fin else (inicio, fin)
    return max(inicio, MIN_AVAILABLE_DATE), max(fin, MIN_AVAILABLE_DATE)
