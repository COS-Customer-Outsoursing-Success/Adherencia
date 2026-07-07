"""Sincroniza los datos del MySQL corporativo hacia Supabase.

Debe ejecutarse periódicamente (Task Scheduler) desde una máquina con acceso
directo al MySQL interno (ej. 172.70.7.60). La app Flask desplegada en Vercel
nunca se conecta al MySQL: solo lee de Supabase, que sí es accesible desde
internet.

La escritura hacia Supabase va por su API REST (HTTPS puerto 443, vía
supabase_rest.py) en vez de la conexión directa Postgres (puertos 5432/6543),
porque la red corporativa bloquea esos puertos. La app desplegada en Vercel
no tiene esa restricción y sigue leyendo por conexión directa (supabase_db.py).

Sincroniza dos conjuntos de datos independientes:
  - attendance_snapshot    -> usado por el dashboard de Ausentismo/Retardos
  - agent_metrics_snapshot -> usado por Excesos y Detalle de Agente
"""
from __future__ import annotations

import logging
import sys

import supabase_rest
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

    payload = [
        {
            "nombre": r.get("Nombre"),
            "supervisor": r.get("Supervisor"),
            "campana": r.get("Campana"),
            "asiste": r.get("Asiste"),
            "ausente": r.get("Ausente"),
            "retardo": r.get("Retardo"),
            "hora_programada": r.get("Hora_Programada"),
            "hora_inicio": r.get("Hora_Inicio"),
            "tiempo_retardo": r.get("Tiempo_Retardo"),
        }
        for r in rows
    ]
    supabase_rest.replace_all("attendance_snapshot", payload)

    logger.info("Sincronización asistencia completa: %d filas escritas en Supabase", len(rows))
    return len(rows)


def sync_agent_metrics() -> int:
    logger.info("Consultando métricas de agentes frescas del MySQL corporativo...")
    rows = execute_query(AGENT_METRICS_SQL)
    logger.info("%d filas obtenidas de MySQL (agent_metrics)", len(rows))

    payload = [
        {
            "nombre": r.get("Nombres_Apellidos"),
            "supervisor": r.get("Supervisor"),
            "campana": r.get("Campana"),
            "llamadas": int(r.get("llamadas") or 0),
            "cant_mrc_inb": int(r.get("Cant_Mrc_Inb") or 0),
            "cant_mrc_out": int(r.get("Cant_Mrc_Out") or 0),
            "ventas_inb": int(r.get("Ventas_Inb") or 0),
            "ventas_out": int(r.get("Ventas_Out") or 0),
            "t_login": r.get("T_login"),
            "t_dispo": r.get("T_dispo"),
            "t_dead": r.get("T_dead"),
            "t_preturno": r.get("T_preturno"),
            "t_capacitacion": r.get("T_capacitacion"),
            "t_whatsapp": r.get("T_whatsapp"),
            "t_exceso_alm": r.get("T_Exceso_Alm"),
            "t_exceso_break": r.get("T_Exceso_Break"),
            "t_exceso_bano": r.get("T_Exceso_Bano"),
            "t_logueado": r.get("T_logueado"),
            "aht": r.get("Aht"),
            "t_acw": r.get("T_acw"),
            "t_espera": r.get("T_espera"),
            "t_pausa_productiva": r.get("T_pausa_productiva"),
            "cantidad_desconexiones": int(r.get("cantidad_desconexiones") or 0),
            "tiempo_desconexion_minutos": r.get("tiempo_desconexion_minutos"),
            "porc_pausa": r.get("Porc_pausa"),
            "ocupacion": r.get("Ocupacion"),
            "disponibilidad": r.get("Disponibilidad"),
            "utilizacion": r.get("Utilizacion"),
            "shrinkage": r.get("Shrinkage"),
            "eficiencia": r.get("Eficiencia"),
        }
        for r in rows
    ]
    supabase_rest.replace_all("agent_metrics_snapshot", payload)

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
