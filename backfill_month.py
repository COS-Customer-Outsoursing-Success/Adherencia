"""Carga inicial (backfill) de días ya transcurridos hacia Supabase.

Se ejecuta una sola vez (a mano) después de agregar la columna `fecha` a
`attendance_snapshot` y `agent_metrics_snapshot`. Recorre día por día, desde el
1 del mes anterior hasta ayer, y reutiliza `sync_to_supabase.sync(fecha)` para
cada uno — así queda histórico disponible sin importar en qué día del mes se
corra este script (cubre tanto la regla de "mes anterior completo" como la de
"mes actual a la fecha").

Debe correrse desde esta máquina, con acceso al MySQL corporativo (igual que
run_sync.bat / Task Scheduler).
"""
from __future__ import annotations

import logging
import sys
from datetime import date, timedelta

import sync_to_supabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _date_range(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def main() -> None:
    today = date.today()
    yesterday = today - timedelta(days=1)
    first_day_prev_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)

    if first_day_prev_month > yesterday:
        logger.info("Nada que hacer: no hay días previos a hoy en el rango.")
        return

    dias = list(_date_range(first_day_prev_month, yesterday))
    logger.info(
        "Backfill de %d día(s): %s → %s",
        len(dias), dias[0].isoformat(), dias[-1].isoformat(),
    )

    fallidos = []
    for d in dias:
        fecha = d.isoformat()
        logger.info("── %s ──", fecha)
        results = sync_to_supabase.sync(fecha)
        if all(v is None for v in results.values()):
            fallidos.append(fecha)

    if fallidos:
        logger.error("Días con error en ambas fuentes: %s", ", ".join(fallidos))
        sys.exit(1)

    logger.info("Backfill completo.")


if __name__ == "__main__":
    main()
