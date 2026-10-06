"""Métricas de agente de Cartera Propia (servidor MySQL secundario, DB2_HOST).

El detalle de agente de Cartera Propia vive en otro servidor que el resto de campañas, así que no
se puede unir con AGENT_METRICS_SQL en un solo SQL. Aquí se lee la tabla cruda de Vicidial de ese
servidor y se devuelven filas con la misma forma que AGENT_METRICS_SQL (tiempos como fracción de día),
para que el sync las escriba en agent_metrics_snapshot junto con las demás.

Limitaciones conocidas: la tabla no trae columna de break (T_break = 0) ni ventas/marcaciones.
"""
from __future__ import annotations

import logging

import mysql.connector

from config import Config
from database import execute_query
from services._queries import ACTIVE_ADVISORS_SQL

logger = logging.getLogger(__name__)

_SQL = """
SELECT
    ID                       AS cedula,
    SUM(CALLS)               AS llamadas,
    SUM(LOGIN_TIME)          AS t_logueado,
    SUM(WAIT)                AS t_espera,
    SUM(TALK)                AS t_charla,
    SUM(DISPO)               AS t_dispo,
    SUM(PAUSE)               AS t_pausa,
    SUM(DEAD)                AS t_dead,
    SUM(CUSTOMER)            AS t_acd,
    SUM(ALMU)                AS t_almuerzo,
    SUM(BANO)                AS t_bano,
    SUM(PAPRO)               AS t_pausa_productiva,
    SUM(PRETU)               AS t_preturno,
    SUM(WHAT)                AS t_whatsapp
FROM bbdd_cs_bog_carteras_propias.tb_detalle_agente_vicidial_groupcos_carteras_propias
WHERE FECHA = %s
  AND Campana = 'Cartera Propia'
GROUP BY ID
"""

DIA = 86400
LIM_ALMUERZO = 40 * 60
LIM_BANO = 15 * 60


def _fetch_secondary(fecha: str) -> list[dict]:
    conn = mysql.connector.connect(
        host=Config.DB2_HOST, port=Config.DB_PORT, user=Config.DB_USERNAME,
        password=Config.DB_PASSWORD, connection_timeout=30, use_pure=True,
    )
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(_SQL, (fecha,))
        return cur.fetchall()
    finally:
        conn.close()


def _ratio(num: float, den: float) -> float:
    return num / den if den else 0.0


def get_metrics(fecha: str) -> list[dict]:
    """Filas tipo AGENT_METRICS_SQL para Cartera Propia (solo asesores del headcount activo)."""
    headcount = {
        str(r["Documento"]).strip(): r
        for r in execute_query(ACTIVE_ADVISORS_SQL)
        if r["Campana"] == "Cartera Propia"
    }

    out = []
    for r in _fetch_secondary(fecha):
        hc = headcount.get(str(r["cedula"]).strip())
        if hc is None:
            continue
        f = {k: float(v or 0) for k, v in r.items() if k != "cedula"}
        acw = f["t_dead"] + f["t_dispo"]
        base_ocup = acw + f["t_acd"]
        util = _ratio(f["t_espera"] + base_ocup + f["t_pausa_productiva"], f["t_logueado"])
        out.append({
            "Nombres_Apellidos": hc["Nombres_Apellidos"],
            "Supervisor": hc["Nombre_Supervisor"],
            "Campana": hc["Campana"],
            "llamadas": int(f["llamadas"]),
            "Cant_Mrc_Inb": 0, "Cant_Mrc_Out": 0, "Ventas_Inb": 0, "Ventas_Out": 0,
            "T_login": 0.0,
            "T_dispo": f["t_dispo"] / DIA,
            "T_dead": f["t_dead"] / DIA,
            "T_preturno": f["t_preturno"] / DIA,
            "T_capacitacion": 0.0,
            "T_whatsapp": f["t_whatsapp"] / DIA,
            "T_Exceso_Alm": max(0.0, f["t_almuerzo"] - LIM_ALMUERZO) / DIA,
            "T_Exceso_Break": 0.0,
            "T_Exceso_Bano": max(0.0, f["t_bano"] - LIM_BANO) / DIA,
            "T_logueado": f["t_logueado"] / DIA,
            "Aht": _ratio(acw + f["t_acd"], f["llamadas"]) / DIA,
            "T_acw": acw / DIA,
            "T_espera": f["t_espera"] / DIA,
            "T_pausa_productiva": f["t_pausa_productiva"] / DIA,
            "cantidad_desconexiones": 0,
            "tiempo_desconexion_minutos": 0,
            "Porc_pausa": _ratio(f["t_pausa"], f["t_logueado"]),
            "Ocupacion": _ratio(base_ocup, base_ocup + f["t_espera"]),
            "Disponibilidad": _ratio(f["t_espera"], base_ocup + f["t_espera"]),
            "Utilizacion": util,
            "Shrinkage": 1 - util,
            "Eficiencia": _ratio(f["t_dispo"] + f["t_acd"], f["t_logueado"]),
        })
    logger.info("Cartera Propia: %d filas de métricas desde %s", len(out), Config.DB2_HOST)
    return out
