"""Sincroniza los datos de asistencia del MySQL corporativo hacia Supabase.

Debe ejecutarse periódicamente (Task Scheduler) desde una máquina con acceso
directo al MySQL interno (ej. 172.70.7.60). La app Flask desplegada en Vercel
nunca se conecta al MySQL: solo lee de Supabase, que sí es accesible desde
internet.
"""
from __future__ import annotations

import logging
import sys

import supabase_db
from services.attendance import get_raw_data_from_mysql

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def sync() -> int:
    logger.info("Consultando datos frescos del MySQL corporativo...")
    rows = get_raw_data_from_mysql()
    logger.info("%d filas obtenidas de MySQL", len(rows))

    with supabase_db.get_cursor() as cur:
        cur.execute("TRUNCATE TABLE attendance_snapshot")
        if rows:
            values = [
                (
                    r.get("Nombre"),
                    r.get("Supervisor"),
                    r.get("Campana"),
                    r.get("Asiste"),
                    r.get("Ausente"),
                    r.get("Retardo"),
                    r.get("Hora_Programada"),
                    r.get("Hora_Inicio"),
                    r.get("Tiempo_Retardo"),
                )
                for r in rows
            ]
            cur.executemany(
                """
                INSERT INTO attendance_snapshot
                    (nombre, supervisor, campana, asiste, ausente, retardo,
                     hora_programada, hora_inicio, tiempo_retardo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                values,
            )

    logger.info("Sincronización completa: %d filas escritas en Supabase", len(rows))
    return len(rows)


if __name__ == "__main__":
    try:
        sync()
    except Exception:
        logger.exception("Error durante la sincronización")
        sys.exit(1)
