from __future__ import annotations

import logging
import os
import random
from datetime import datetime

import supabase_db
from services._queries import AGENT_METRICS_SNAPSHOT_SQL
from utils.formatters import safe_pct, seconds_to_hhmmss

logger = logging.getLogger(__name__)



_MOCK_SUPERVISORES = ["Kimberli Tatiana Maldonado Rincon", "Guillermo Rojas Correa", "Kevin David Rosero Buitrago"]
_MOCK_CAMPANAS = ["Claro - Hogar Tmk Bogota", "Claro - Movil Tmk Bogota"]
_MOCK_NOMBRES = [
    "Bryan David Aguirre Osorio", "Sergio Eduardo Rojas Duarte", "Laura Juliana Plazas Ipuz",
    "Yeferson Alejandro Rojas Bohorquez", "Williams Enrique Bastidas Diaz", "Dayana Vanessa Contreras Tellez",
    "Erick Stiven Martinez Zapata", "Juan Jose Lugo Benavides", "Heidi Maiyuri Salamanca Murillo",
    "Yeraldin Paez Florez", "Jelahine Garzon Gomez", "Nicole Alejandra Rueda Ramirez",
]


def _seconds_frac(seconds: float) -> float:
    """Inverso de _day_frac_to_seconds: convierte segundos a fracción de día (como los devuelve la query real)."""
    return seconds / 86400.0


def _mock_raw_rows() -> list[dict]:
    """Filas de muestra con la misma forma que devuelve AGENT_METRICS_SQL. Solo para previsualizar la interfaz
    mientras el MySQL corporativo no está disponible. Activar con EXCESOS_MOCK=1."""
    rng = random.Random(42)
    rows = []
    for nombre in _MOCK_NOMBRES:
        t_login = rng.uniform(6, 9) * 3600
        t_dispo = t_login * rng.uniform(0.5, 0.75)
        t_almuerzo = rng.uniform(20, 55) * 60
        t_break = rng.uniform(10, 25) * 60
        t_bano = rng.uniform(3, 18) * 60
        rows.append({
            "Nombres_Apellidos": nombre,
            "Supervisor": rng.choice(_MOCK_SUPERVISORES),
            "Campana": rng.choice(_MOCK_CAMPANAS),
            "T_login": _seconds_frac(t_login),
            "T_dispo": _seconds_frac(t_dispo),
            "T_dead": _seconds_frac(rng.uniform(0, 6) * 60),
            "T_preturno": _seconds_frac(rng.uniform(0, 10) * 60),
            "T_capacitacion": _seconds_frac(rng.uniform(0, 30) * 60),
            "T_whatsapp": _seconds_frac(rng.uniform(0, 15) * 60),
            "T_almuerzo": _seconds_frac(t_almuerzo),
            "T_Exceso_Alm": _seconds_frac(max(0, t_almuerzo - 45 * 60)),
            "T_Exceso_Break": _seconds_frac(max(0, t_break - 20 * 60)),
            "T_Exceso_Bano": _seconds_frac(max(0, t_bano - 15 * 60)),
        })
    return rows


def _day_frac_to_seconds(value) -> float:
    """Convierte una fracción de día (value/86400 en SQL) de vuelta a segundos."""
    return float(value or 0) * 86400.0


def _build_row(r: dict) -> dict:
    t_login_seg = _day_frac_to_seconds(r.get("T_login"))
    t_pantalla_verde_seg = _day_frac_to_seconds(r.get("T_dispo"))
    t_dead_seg = _day_frac_to_seconds(r.get("T_dead"))
    t_preturno_seg = _day_frac_to_seconds(r.get("T_preturno"))
    t_capacitacion_seg = _day_frac_to_seconds(r.get("T_capacitacion"))
    t_whatsapp_seg = _day_frac_to_seconds(r.get("T_whatsapp"))
    t_exceso_alm_seg = _day_frac_to_seconds(r.get("T_Exceso_Alm"))
    t_exceso_break_seg = _day_frac_to_seconds(r.get("T_Exceso_Break"))
    t_exceso_bano_seg = _day_frac_to_seconds(r.get("T_Exceso_Bano"))
    t_exceso_total_seg = t_exceso_alm_seg + t_exceso_break_seg + t_exceso_bano_seg

    return {
        "Asesor": r.get("Nombres_Apellidos"),
        "Supervisor": r.get("Supervisor"),
        "Campana": r.get("Campana"),

        "T_login": seconds_to_hhmmss(t_login_seg),
        "T_login_seg": round(t_login_seg, 1),

        "T_Pantalla_Verde": seconds_to_hhmmss(t_pantalla_verde_seg),
        "T_Pantalla_Verde_seg": round(t_pantalla_verde_seg, 1),

        "T_dead": seconds_to_hhmmss(t_dead_seg),
        "T_dead_seg": round(t_dead_seg, 1),

        "T_preturno": seconds_to_hhmmss(t_preturno_seg),
        "T_preturno_seg": round(t_preturno_seg, 1),

        "T_capacitacion": seconds_to_hhmmss(t_capacitacion_seg),
        "T_capacitacion_seg": round(t_capacitacion_seg, 1),

        "T_whatsapp": seconds_to_hhmmss(t_whatsapp_seg),
        "T_whatsapp_seg": round(t_whatsapp_seg, 1),

        "T_Exceso_Alm": seconds_to_hhmmss(t_exceso_alm_seg),
        "T_Exceso_Alm_seg": round(t_exceso_alm_seg, 1),

        "T_Exceso_Break": seconds_to_hhmmss(t_exceso_break_seg),
        "T_Exceso_Break_seg": round(t_exceso_break_seg, 1),

        "T_Exceso_Bano": seconds_to_hhmmss(t_exceso_bano_seg),
        "T_Exceso_Bano_seg": round(t_exceso_bano_seg, 1),

        "T_Exceso_Total": seconds_to_hhmmss(t_exceso_total_seg),
        "T_Exceso_Total_seg": round(t_exceso_total_seg, 1),
    }


def _apply_filters(rows: list[dict], filters: dict) -> list[dict]:
    result = rows
    if filters.get("supervisor"):
        result = [r for r in result if r["Supervisor"] == filters["supervisor"]]
    if filters.get("campana"):
        result = [r for r in result if r["Campana"] == filters["campana"]]
    if filters.get("solo_con_exceso"):
        result = [r for r in result if r["T_Exceso_Total_seg"] > 0]
    return result


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
        "campanas": sorted({r["Campana"] for r in data if r["Campana"]}),
    }


def get_kpis(data: list[dict] | None = None) -> dict:
    if data is None:
        data = get_raw_data()
    total_agentes = len(data)
    con_exceso = sum(1 for r in data if r["T_Exceso_Total_seg"] > 0)
    total_alm_seg = sum(r["T_Exceso_Alm_seg"] for r in data)
    total_break_seg = sum(r["T_Exceso_Break_seg"] for r in data)
    total_bano_seg = sum(r["T_Exceso_Bano_seg"] for r in data)
    total_exceso_seg = total_alm_seg + total_break_seg + total_bano_seg
    return {
        "total_agentes": total_agentes,
        "agentes_con_exceso": con_exceso,
        "pct_con_exceso": safe_pct(con_exceso, total_agentes),
        "total_exceso_min": round(total_exceso_seg / 60, 1),
        "total_exceso_alm_min": round(total_alm_seg / 60, 1),
        "total_exceso_break_min": round(total_break_seg / 60, 1),
        "total_exceso_bano_min": round(total_bano_seg / 60, 1),
    }


def get_supervisor_summary(data: list[dict] | None = None) -> list[dict]:
    if data is None:
        data = get_raw_data()
    acc: dict[str, dict] = {}
    for r in data:
        s = r["Supervisor"] or "Sin asignar"
        if s not in acc:
            acc[s] = {
                "supervisor": s, "agentes": 0, "con_exceso": 0,
                "exceso_alm_min": 0.0, "exceso_break_min": 0.0,
                "exceso_bano_min": 0.0, "exceso_total_min": 0.0,
            }
        acc[s]["agentes"] += 1
        if r["T_Exceso_Total_seg"] > 0:
            acc[s]["con_exceso"] += 1
        acc[s]["exceso_alm_min"] += r["T_Exceso_Alm_seg"] / 60
        acc[s]["exceso_break_min"] += r["T_Exceso_Break_seg"] / 60
        acc[s]["exceso_bano_min"] += r["T_Exceso_Bano_seg"] / 60
        acc[s]["exceso_total_min"] += r["T_Exceso_Total_seg"] / 60

    result = list(acc.values())
    for s in result:
        for k in ("exceso_alm_min", "exceso_break_min", "exceso_bano_min", "exceso_total_min"):
            s[k] = round(s[k], 1)
    result.sort(key=lambda x: x["exceso_total_min"], reverse=True)
    return result


def get_full_report(filters: dict | None = None) -> dict:
    data = get_raw_data(filters)
    return {
        "kpis": get_kpis(data),
        "supervisors": get_supervisor_summary(data),
        "agentes": data,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_records": len(data),
    }
