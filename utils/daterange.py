from __future__ import annotations

from datetime import date

# Fecha más antigua con histórico cargado (inicio del backfill inicial). No hay
# datos antes de esto, así que ninguna fecha resuelta debe quedar por debajo.
MIN_AVAILABLE_DATE = "2026-08-01"


def default_range() -> tuple[str, str]:
    """Rango por defecto cuando el usuario no elige fechas: siempre hoy."""
    today = date.today().isoformat()
    return today, today


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
