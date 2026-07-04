"""Sincroniza los datos del MySQL corporativo hacia Supabase.

Debe ejecutarse periódicamente (Task Scheduler) desde una máquina con acceso
directo al MySQL interno (ej. 172.70.7.60). La app Flask desplegada en Vercel
nunca se conecta al MySQL: solo lee de Supabase, que sí es accesible desde
internet.

Sincroniza dos conjuntos de datos independientes:
  - attendance_snapshot   -> usado por el dashboard de Ausentismo/Retardos
  - agent_metrics_snapshot -> usado por Excesos y Detalle de Agente
"""
from __future__ import annotations

import logging
import sys

import supabase_db
from database import execute_query
from services._queries import AGENT_METRICS_SQL
from services.attendance import get_raw_data_from_mysql

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def sync_attendance() -> int:
    logger.info("Consultando datos de asistencia frescos del MySQL corporativo...")
    rows = get_raw_data_from_mysql()
    logger.info("%d filas obtenidas de MySQL (asistencia)", len(rows))

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

    logger.info("Sincronización asistencia completa: %d filas escritas en Supabase", len(rows))
    return len(rows)


def sync_agent_metrics() -> int:
    logger.info("Consultando métricas de agentes frescas del MySQL corporativo...")
    rows = execute_query(AGENT_METRICS_SQL)
    logger.info("%d filas obtenidas de MySQL (agent_metrics)", len(rows))

    with supabase_db.get_cursor() as cur:
        cur.execute("TRUNCATE TABLE agent_metrics_snapshot")
        if rows:
            values = [
                (
                    r.get("Nombres_Apellidos"),
                    r.get("Supervisor"),
                    r.get("Campana"),
                    r.get("llamadas"),
                    r.get("Cant_Mrc_Inb"),
                    r.get("Cant_Mrc_Out"),
                    r.get("Ventas_Inb"),
                    r.get("Ventas_Out"),
                    r.get("T_login"),
                    r.get("T_dispo"),
                    r.get("T_dead"),
                    r.get("T_preturno"),
                    r.get("T_capacitacion"),
                    r.get("T_whatsapp"),
                    r.get("T_Exceso_Alm"),
                    r.get("T_Exceso_Break"),
                    r.get("T_Exceso_Bano"),
                    r.get("T_logueado"),
                    r.get("Aht"),
                    r.get("T_acw"),
                    r.get("T_espera"),
                    r.get("T_pausa_productiva"),
                    r.get("cantidad_desconexiones"),
                    r.get("tiempo_desconexion_minutos"),
                    r.get("Porc_pausa"),
                    r.get("Ocupacion"),
                    r.get("Disponibilidad"),
                    r.get("Utilizacion"),
                    r.get("Shrinkage"),
                    r.get("Eficiencia"),
                )
                for r in rows
            ]
            cur.executemany(
                """
                INSERT INTO agent_metrics_snapshot
                    (nombre, supervisor, campana, llamadas, cant_mrc_inb, cant_mrc_out,
                     ventas_inb, ventas_out, t_login, t_dispo, t_dead, t_preturno,
                     t_capacitacion, t_whatsapp, t_exceso_alm, t_exceso_break, t_exceso_bano,
                     t_logueado, aht, t_acw, t_espera, t_pausa_productiva,
                     cantidad_desconexiones, tiempo_desconexion_minutos,
                     porc_pausa, ocupacion, disponibilidad, utilizacion, shrinkage, eficiencia)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                values,
            )

    logger.info("Sincronización agent_metrics completa: %d filas escritas en Supabase", len(rows))
    return len(rows)


def sync() -> dict:
    results = {}

    try:
        results["attendance"] = sync_attendance()
    except Exception:
        logger.exception("Error sincronizando asistencia")
        results["attendance"] = None

    try:
        results["agent_metrics"] = sync_agent_metrics()
    except Exception:
        logger.exception("Error sincronizando métricas de agentes")
        results["agent_metrics"] = None

    return results


if __name__ == "__main__":
    results = sync()
    if all(v is None for v in results.values()):
        sys.exit(1)
