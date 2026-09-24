from __future__ import annotations

import logging
import os
import random
from datetime import datetime

import supabase_db
import supabase_rest
from services._queries import AGENT_METRICS_SNAPSHOT_SQL, TYT_SALES_SNAPSHOT_SQL
from utils.daterange import resolve_date_range
from utils.formatters import date_to_str, safe_pct, seconds_to_hhmmss

logger = logging.getLogger(__name__)

def fetch_tyt_data(fecha_inicio: str, fecha_fin: str) -> dict:
    """Ventas TyT acumuladas por asesor en el rango, leídas del snapshot en Supabase."""
    try:
        try:
            rows = supabase_db.execute_query(TYT_SALES_SNAPSHOT_SQL, (fecha_inicio, fecha_fin))
        except Exception as e:
            logger.warning(f"Error con conexión Postgres directa en ventas TyT: {e}. Reintentando con API REST...")
            rows = supabase_rest.fetch_tyt_sales(fecha_inicio, fecha_fin)
    except Exception as e:
        logger.error(f"Error obteniendo ventas TyT: {e}")
        return {}

    # La vía REST trae una fila por día: se acumula por asesor.
    result: dict[str, dict] = {}
    for r in rows:
        ag = result.setdefault(r["Asesor"], {"Asesor": r["Asesor"]})
        for k in ("Terminales", "Tecnologia", "Unidades", "Dolar_Terminales", "Dolar_Tecnologia", "Dolar_Total"):
            ag[k] = ag.get(k, 0) + float(r.get(k) or 0)
    return result


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
        "Fecha": date_to_str(r.get("Fecha")),
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
        result = [r for r in result if r["Supervisor"] in filters["supervisor"]]
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
            "Fecha": datetime.now().date().isoformat(),
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
    filters = filters or {}
    if os.getenv("EXCESOS_MOCK") == "1":
        logger.warning("EXCESOS_MOCK=1: usando datos de muestra, NO son datos reales de MySQL")
        rows = _mock_raw_rows()
    else:
        fecha_inicio, fecha_fin = resolve_date_range(filters)
        try:
            rows = supabase_db.execute_query(AGENT_METRICS_SNAPSHOT_SQL, (fecha_inicio, fecha_fin))
        except Exception as e:
            logger.warning(f"Error con conexión Postgres directa en detalle_agente: {e}. Reintentando con API REST...")
            rows = supabase_rest.fetch_agent_metrics(fecha_inicio, fecha_fin)

    built = [_build_row(r) for r in rows]
    return _apply_filters(built, filters)


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
        "total_agentes": len({r["Asesor"] for r in data}),
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
    
    agent_map = {}
    for r in data:
        key = (r["Asesor"], r["Supervisor"], r["Campana"])
        if key not in agent_map:
            agent_map[key] = {
                "Asesor": r["Asesor"],
                "Supervisor": r["Supervisor"],
                "Campana": r["Campana"],
                "count": 0,
                "T_logueado_seg": 0,
                "Llamadas": 0,
                "Llamadas_Inb": 0,
                "Llamadas_Out": 0,
                "Ventas_Inb": 0,
                "Ventas_Out": 0,
                "T_AHT_seg": 0,
                "T_ACW_seg": 0,
                "T_Espera_seg": 0,
                "T_Pausa_Produ_seg": 0,
                "Cant_Desconex": 0,
                "T_Desconex_seg": 0,
                "Pct_Pausa": 0,
                "Pct_Ocupacion": 0,
                "Pct_Disponibilidad": 0,
                "Pct_Utilizacion": 0,
                "Pct_Shrinkage": 0,
                "Pct_Eficiencia": 0,
            }
        
        ag = agent_map[key]
        ag["count"] += 1
        
        ag["T_logueado_seg"] += r["T_logueado_seg"]
        ag["Llamadas"] += r["Llamadas"]
        ag["Llamadas_Inb"] += r["Llamadas_Inb"]
        ag["Llamadas_Out"] += r["Llamadas_Out"]
        ag["Ventas_Inb"] += r["Ventas_Inb"]
        ag["Ventas_Out"] += r["Ventas_Out"]
        
        ag["T_AHT_seg"] += r["T_AHT_seg"]
        ag["T_ACW_seg"] += r["T_ACW_seg"]
        ag["T_Espera_seg"] += r["T_Espera_seg"]
        ag["T_Pausa_Produ_seg"] += r["T_Pausa_Produ_seg"]
        ag["Cant_Desconex"] += r["Cant_Desconex"]
        ag["T_Desconex_seg"] += r["T_Desconex_seg"]
        
        ag["Pct_Pausa"] += r["Pct_Pausa"]
        ag["Pct_Ocupacion"] += r["Pct_Ocupacion"]
        ag["Pct_Disponibilidad"] += r["Pct_Disponibilidad"]
        ag["Pct_Utilizacion"] += r["Pct_Utilizacion"]
        ag["Pct_Shrinkage"] += r["Pct_Shrinkage"]
        ag["Pct_Eficiencia"] += r["Pct_Eficiencia"]

    fecha_inicio, fecha_fin = resolve_date_range(filters or {})
    fecha_str = f"{fecha_inicio} a {fecha_fin}" if fecha_inicio != fecha_fin else fecha_inicio

    is_tyt = (filters or {}).get("campana") == "Claro - Terminales & Tecnologia Bogota"
    tyt_data = {}
    if is_tyt:
        tyt_data = fetch_tyt_data(fecha_inicio, fecha_fin)

    agentes_agrupados = []
    for ag in agent_map.values():
        c = ag["count"]
        ag["Fecha"] = fecha_str
        
        ag["T_logueado"] = seconds_to_hhmmss(ag["T_logueado_seg"])
        
        ag["T_AHT_seg"] = ag["T_AHT_seg"] / c if c > 0 else 0
        ag["T_AHT"] = seconds_to_hhmmss(ag["T_AHT_seg"])
        
        ag["T_ACW"] = seconds_to_hhmmss(ag["T_ACW_seg"])
        ag["T_Espera"] = seconds_to_hhmmss(ag["T_Espera_seg"])
        ag["T_Pausa_Produ"] = seconds_to_hhmmss(ag["T_Pausa_Produ_seg"])
        
        ag["T_Desconex_seg"] = ag["T_Desconex_seg"] / c if c > 0 else 0
        ag["T_Desconex"] = seconds_to_hhmmss(ag["T_Desconex_seg"])
        
        ag["Pct_Pausa"] = round(ag["Pct_Pausa"] / c, 1) if c > 0 else 0
        ag["Pct_Ocupacion"] = round(ag["Pct_Ocupacion"] / c, 1) if c > 0 else 0
        ag["Pct_Disponibilidad"] = round(ag["Pct_Disponibilidad"] / c, 1) if c > 0 else 0
        ag["Pct_Utilizacion"] = round(ag["Pct_Utilizacion"] / c, 1) if c > 0 else 0
        ag["Pct_Shrinkage"] = round(ag["Pct_Shrinkage"] / c, 1) if c > 0 else 0
        ag["Pct_Eficiencia"] = round(ag["Pct_Eficiencia"] / c, 1) if c > 0 else 0
        
        if is_tyt:
            tyt = tyt_data.get(ag["Asesor"], {})
            unidades = float(tyt.get("Unidades", 0) or 0)
            ag["TyT_Terminales"] = int(tyt.get("Terminales", 0) or 0)
            ag["TyT_Tecnologia"] = int(tyt.get("Tecnologia", 0) or 0)
            ag["TyT_Unidades"] = int(unidades)
            ag["TyT_Efect_Grl"] = round(unidades / ag["Llamadas"], 4) if ag["Llamadas"] > 0 else 0
            ag["TyT_Dolar_Terminales"] = float(tyt.get("Dolar_Terminales", 0) or 0)
            ag["TyT_Dolar_Tecnologia"] = float(tyt.get("Dolar_Tecnologia", 0) or 0)
            ag["TyT_Dolar_Total"] = float(tyt.get("Dolar_Total", 0) or 0)
            
        del ag["count"]
        agentes_agrupados.append(ag)

    agentes_agrupados.sort(key=lambda x: x["Asesor"])

    return {
        "kpis": get_kpis(data),
        "agentes": agentes_agrupados,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_records": len(agentes_agrupados),
    }
