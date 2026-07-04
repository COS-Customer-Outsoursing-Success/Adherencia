from __future__ import annotations

import logging
import os
import random
from datetime import datetime

import supabase_db
from services._queries import AGENT_METRICS_SNAPSHOT_SQL
from utils.formatters import safe_pct, seconds_to_hhmmss

logger = logging.getLogger(__name__)


def _day_frac_to_seconds(value) -> float:
    return float(value or 0) * 86400.0


def _pct(ratio) -> float:
    return round(float(ratio or 0) * 100, 1)


def _build_row(r: dict) -> dict:
    t_logueado_seg = _day_frac_to_seconds(r.get("T_logueado"))
    t_aht_seg      = _day_frac_to_seconds(r.get("Aht"))
    t_acw_seg      = _day_frac_to_seconds(r.get("T_acw"))
    t_espera_seg   = _day_frac_to_seconds(r.get("T_espera"))
    t_pausa_prod_seg = _day_frac_to_seconds(r.get("T_pausa_productiva"))
    t_desconex_seg = _day_frac_to_seconds(r.get("tiempo_desconexion_minutos"))

    return {
        "Asesor": r.get("Nombres_Apellidos"),
        "Supervisor": r.get("Supervisor"),
        "Campana": r.get("Campana"),

        "T_logueado": seconds_to_hhmmss(t_logueado_seg),
        "T_logueado_seg": round(t_logueado_seg, 1),

        "Llamadas": int(r.get("llamadas") or 0),
        "Llamadas_Inb": int(r.get("Cant_Mrc_Inb") or 0),
        "Llamadas_Out": int(r.get("Cant_Mrc_Out") or 0),
        "Ventas_Inb": int(r.get("Ventas_Inb") or 0),
        "Ventas_Out": int(r.get("Ventas_Out") or 0),

        "T_AHT": seconds_to_hhmmss(t_aht_seg),
        "T_AHT_seg": round(t_aht_seg, 1),

        "T_ACW": seconds_to_hhmmss(t_acw_seg),
        "T_ACW_seg": round(t_acw_seg, 1),

        "T_Espera": seconds_to_hhmmss(t_espera_seg),
        "T_Espera_seg": round(t_espera_seg, 1),

        "T_Pausa_Produ": seconds_to_hhmmss(t_pausa_prod_seg),
        "T_Pausa_Produ_seg": round(t_pausa_prod_seg, 1),

        "Cant_Desconex": int(r.get("cantidad_desconexiones") or 0),

        "T_Desconex": seconds_to_hhmmss(t_desconex_seg),
        "T_Desconex_seg": round(t_desconex_seg, 1),

        "Pct_Pausa": _pct(r.get("Porc_pausa")),
        "Pct_Ocupacion": _pct(r.get("Ocupacion")),
        "Pct_Disponibilidad": _pct(r.get("Disponibilidad")),
        "Pct_Utilizacion": _pct(r.get("Utilizacion")),
        "Pct_Shrinkage": _pct(r.get("Shrinkage")),
        "Pct_Eficiencia": _pct(r.get("Eficiencia")),
    }


def _apply_filters(rows: list[dict], filters: dict) -> list[dict]:
    result = rows
    if filters.get("supervisor"):
        result = [r for r in result if r["Supervisor"] == filters["supervisor"]]
    if filters.get("campana"):
        result = [r for r in result if r["Campana"] == filters["campana"]]
    return result


_MOCK_SUPERVISORES = ["Kimberli Tatiana Maldonado Rincon", "Guillermo Rojas Correa", "Kevin David Rosero Buitrago"]
_MOCK_CAMPANAS = ["Claro - Hogar Tmk Bogota", "Claro - Movil Tmk Bogota"]
_MOCK_NOMBRES = [
    "Bryan David Aguirre Osorio", "Sergio Eduardo Rojas Duarte", "Laura Juliana Plazas Ipuz",
    "Yeferson Alejandro Rojas Bohorquez", "Williams Enrique Bastidas Diaz", "Dayana Vanessa Contreras Tellez",
    "Erick Stiven Martinez Zapata", "Juan Jose Lugo Benavides", "Heidi Maiyuri Salamanca Murillo",
    "Yeraldin Paez Florez", "Jelahine Garzon Gomez", "Nicole Alejandra Rueda Ramirez",
]


def _mock_raw_rows() -> list[dict]:
    """Filas de muestra con la misma forma que devuelve AGENT_METRICS_SQL.
    Solo para previsualizar la interfaz mientras el MySQL corporativo no está disponible.
    Activar con EXCESOS_MOCK=1."""
    rng = random.Random(7)
    rows = []
    for nombre in _MOCK_NOMBRES:
        t_logueado = rng.uniform(6, 9) * 3600
        llamadas = rng.randint(60, 160)
        rows.append({
            "Nombres_Apellidos": nombre,
            "Supervisor": rng.choice(_MOCK_SUPERVISORES),
            "Campana": rng.choice(_MOCK_CAMPANAS),
            "T_logueado": t_logueado / 86400,
            "llamadas": llamadas,
            "Cant_Mrc_Inb": int(llamadas * rng.uniform(0.3, 0.6)),
            "Cant_Mrc_Out": int(llamadas * rng.uniform(0.4, 0.7)),
            "Ventas_Inb": rng.randint(0, 8),
            "Ventas_Out": rng.randint(0, 10),
            "Aht": rng.uniform(60, 240) / 86400,
            "T_acw": rng.uniform(300, 1800) / 86400,
            "T_espera": rng.uniform(600, 3600) / 86400,
            "T_pausa_productiva": rng.uniform(0, 900) / 86400,
            "cantidad_desconexiones": rng.randint(0, 6),
            "tiempo_desconexion_minutos": rng.uniform(0, 1800) / 86400,
            "Porc_pausa": rng.uniform(0.05, 0.4),
            "Ocupacion": rng.uniform(0.4, 0.9),
            "Disponibilidad": rng.uniform(0.1, 0.4),
            "Utilizacion": rng.uniform(0.4, 0.85),
            "Shrinkage": rng.uniform(0.1, 0.5),
            "Eficiencia": rng.uniform(0.3, 0.75),
        })
    return rows


# ── Funciones públicas ──────────────────────────────────────────────────────

def get_raw_data(filters: dict | None = None) -> list[dict]:
    if os.getenv("EXCESOS_MOCK") == "1":
        logger.warning("EXCESOS_MOCK=1: usando datos de muestra, NO son datos reales de MySQL")
        rows = _mock_raw_rows()
    else:
        rows = supabase_db.execute_query(AGENT_METRICS_SNAPSHOT_SQL)
    built = [_build_row(r) for r in rows]
    return _apply_filters(built, filters or {})


def get_filter_options() -> dict:
    data = get_raw_data()
    return {
        "supervisors": sorted({r["Supervisor"] for r in data if r["Supervisor"]}),
        "campanas":    sorted({r["Campana"]    for r in data if r["Campana"]}),
    }


def get_kpis(data: list[dict] | None = None) -> dict:
    if data is None:
        data = get_raw_data()
    total = len(data)
    if total == 0:
        return {
            "total_agentes": 0, "total_llamadas": 0, "total_ventas": 0,
            "total_desconexiones": 0, "aht_prom": "00:00:00", "desconex_prom": "00:00:00",
            "pct_ocupacion": 0, "pct_disponibilidad": 0, "pct_pausa": 0,
            "pct_eficiencia": 0, "pct_utilizacion": 0, "pct_shrinkage": 0,
        }

    total_llamadas = sum(r["Llamadas"] for r in data)
    total_ventas = sum(r["Ventas_Inb"] + r["Ventas_Out"] for r in data)
    total_desconexiones = sum(r["Cant_Desconex"] for r in data)
    aht_prom_seg = sum(r["T_AHT_seg"] for r in data) / total
    desconex_prom_seg = sum(r["T_Desconex_seg"] for r in data) / total

    return {
        "total_agentes": total,
        "total_llamadas": total_llamadas,
        "total_ventas": total_ventas,
        "total_desconexiones": total_desconexiones,
        "aht_prom": seconds_to_hhmmss(aht_prom_seg),
        "desconex_prom": seconds_to_hhmmss(desconex_prom_seg),
        "pct_ocupacion":      round(sum(r["Pct_Ocupacion"]      for r in data) / total, 1),
        "pct_disponibilidad": round(sum(r["Pct_Disponibilidad"] for r in data) / total, 1),
        "pct_pausa":          round(sum(r["Pct_Pausa"]          for r in data) / total, 1),
        "pct_eficiencia":     round(sum(r["Pct_Eficiencia"]     for r in data) / total, 1),
        "pct_utilizacion":    round(sum(r["Pct_Utilizacion"]    for r in data) / total, 1),
        "pct_shrinkage":      round(sum(r["Pct_Shrinkage"]      for r in data) / total, 1),
    }


def get_full_report(filters: dict | None = None) -> dict:
    data = get_raw_data(filters)
    return {
        "kpis": get_kpis(data),
        "agentes": data,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_records": len(data),
    }
