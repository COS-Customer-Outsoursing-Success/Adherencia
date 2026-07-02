from __future__ import annotations

import logging
from typing import Any

from database import execute_query
from utils.formatters import td_to_str, safe_pct, hhmmss_to_minutes

logger = logging.getLogger(__name__)

# Campañas monitoreadas
CAMPANAS = (
    "Claro - Movil Tmk Bogota",
    "Claro / Hogar Tmk Bogota",
    "Claro - Hogar Tmk Bogota",
    "Claro - Terminales & Tecnologia Bogota",
)

_BASE_SQL = """
SELECT
    HC.Nombres_Apellidos          AS Nombre,
    HC.Nombre_Supervisor          AS Supervisor,
    HC.Campana                    AS Campana,
    IF(SOUL.hora_log_ini_turn > 0, 1, 0) AS Asiste,
    CASE
        WHEN SOUL.hora_log_ini_turn = 0
         AND SOUL.hora_prog_ini_turn <= SOUL.fecha_insert
        THEN 1 ELSE 0
    END                           AS Ausente,
    IF(
        TIMESTAMPDIFF(SECOND, SOUL.hora_prog_ini_turn, SOUL.hora_log_ini_turn) > 60,
        1, 0
    )                             AS Retardo,
    SOUL.hora_prog_ini_turn       AS Hora_Programada,
    SOUL.hora_log_ini_turn        AS Hora_Inicio,
    IF(
        SOUL.Hora_Prog_Ini_Turn < SOUL.Hora_Log_Ini_Turn,
        TIMEDIFF(SOUL.Hora_Log_Ini_Turn, SOUL.Hora_Prog_Ini_Turn),
        MAKETIME(0,0,0)
    )                             AS Tiempo_Retardo
FROM bbdd_config.tb_headcount HC
INNER JOIN bbdd_config.tb_soul_proglog SOUL
       ON HC.documento = SOUL.documento
WHERE HC.Campana IN ({placeholders})
  AND HC.Estado = 'Activo'
  AND HC.Cargo  = 'Asesor'
  AND SOUL.fecha_prog_ini_turn = CURDATE()
  AND SOUL.hora_prog_ini_turn  > 0
"""


def _build_query() -> tuple[str, tuple]:
    placeholders = ", ".join(["%s"] * len(CAMPANAS))
    return _BASE_SQL.format(placeholders=placeholders), CAMPANAS


def _serialize_row(row: dict) -> dict:
    """Convierte tipos MySQL no-JSON (timedelta) a strings."""
    return {
        **row,
        "Hora_Programada": td_to_str(row.get("Hora_Programada")),
        "Hora_Inicio":     td_to_str(row.get("Hora_Inicio")),
        "Tiempo_Retardo":  td_to_str(row.get("Tiempo_Retardo")),
    }


def _apply_filters(rows: list[dict], filters: dict) -> list[dict]:
    result = rows

    if filters.get("supervisor"):
        result = [r for r in result if r["Supervisor"] == filters["supervisor"]]

    if filters.get("campana"):
        result = [r for r in result if r["Campana"] == filters["campana"]]

    estado = filters.get("estado")
    if estado == "Asistio":
        result = [r for r in result if r["Asiste"] == 1 and r["Retardo"] == 0]
    elif estado == "Ausente":
        result = [r for r in result if r["Ausente"] == 1]
    elif estado == "Retardo":
        result = [r for r in result if r["Retardo"] == 1]

    hora_ini = filters.get("hora_inicio")
    hora_fin = filters.get("hora_fin")
    if hora_ini and hora_fin:
        result = [
            r for r in result
            if r["Hora_Inicio"] and hora_ini <= r["Hora_Inicio"] <= hora_fin
        ]

    return result


# ── Funciones públicas ──────────────────────────────────────────────────────

def get_raw_data(filters: dict | None = None) -> list[dict]:
    sql, params = _build_query()
    rows = execute_query(sql, params)
    serialized = [_serialize_row(r) for r in rows]
    return _apply_filters(serialized, filters or {})


def get_kpis(data: list[dict] | None = None) -> dict:
    if data is None:
        data = get_raw_data()
    total   = len(data)
    asist   = sum(1 for r in data if r["Asiste"]   == 1)
    ausen   = sum(1 for r in data if r["Ausente"]  == 1)
    retard  = sum(1 for r in data if r["Retardo"]  == 1)
    # Puntuales = asistieron sin retardo
    puntual = asist - retard
    return {
        "total_programados": total,
        "total_asistieron":  asist,
        "total_ausentes":    ausen,
        "total_retardos":    retard,
        "pct_ausentismo":    safe_pct(ausen,  total),
        "pct_puntualidad":   safe_pct(puntual, total),
        "pct_retardos":      safe_pct(retard,  total),
    }


def get_supervisor_summary(data: list[dict] | None = None) -> list[dict]:
    if data is None:
        data = get_raw_data()
    acc: dict[str, dict] = {}
    for r in data:
        s = r["Supervisor"] or "Sin asignar"
        if s not in acc:
            acc[s] = {"supervisor": s, "programados": 0, "asistieron": 0,
                      "ausentes": 0, "retardos": 0}
        acc[s]["programados"] += 1
        if r["Asiste"]  == 1: acc[s]["asistieron"] += 1
        if r["Ausente"] == 1: acc[s]["ausentes"]   += 1
        if r["Retardo"] == 1: acc[s]["retardos"]   += 1

    result = []
    for stats in acc.values():
        p = stats["programados"]
        stats["pct_ausentismo"] = safe_pct(stats["ausentes"],   p)
        stats["pct_retardo"]    = safe_pct(stats["retardos"],   p)
        stats["pct_asistencia"] = safe_pct(stats["asistieron"], p)
        result.append(stats)

    result.sort(key=lambda x: x["pct_ausentismo"], reverse=True)
    return result


def get_timeline(data: list[dict] | None = None) -> dict:
    if data is None:
        data = get_raw_data()
    buckets: dict[str, int] = {}
    for r in data:
        hora = r.get("Hora_Inicio")
        if hora and hora != "00:00:00":
            hhmm = hora[:5]
            buckets[hhmm] = buckets.get(hhmm, 0) + 1
    sorted_items = sorted(buckets.items())
    return {
        "labels": [i[0] for i in sorted_items],
        "values": [i[1] for i in sorted_items],
    }


def get_ausentismo(data: list[dict] | None = None) -> dict:
    """Sección exclusiva de ausentismo: total, listado y ausentes por supervisor."""
    if data is None:
        data = get_raw_data()
    absentees = [r for r in data if r["Ausente"] == 1]
    absentees_sorted = sorted(
        absentees, key=lambda r: (r["Supervisor"] or "", r["Nombre"] or "")
    )

    by_sup: dict[str, int] = {}
    for r in absentees:
        s = r["Supervisor"] or "Sin asignar"
        by_sup[s] = by_sup.get(s, 0) + 1
    by_supervisor = sorted(
        [{"supervisor": s, "ausentes": c} for s, c in by_sup.items()],
        key=lambda x: x["ausentes"], reverse=True,
    )

    return {
        "total": len(absentees),
        "list": [
            {
                "Nombre": r["Nombre"],
                "Supervisor": r["Supervisor"],
                "Hora_Programada": r["Hora_Programada"],
            }
            for r in absentees_sorted
        ],
        "by_supervisor": by_supervisor,
    }


def get_retardos_detalle(data: list[dict] | None = None) -> dict:
    """Sección exclusiva de retardos: total, listado (mayor a menor) y promedio por supervisor."""
    if data is None:
        data = get_raw_data()
    latecomers = [r for r in data if r["Retardo"] == 1]

    enriched = []
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for r in latecomers:
        minutos = hhmmss_to_minutes(r.get("Tiempo_Retardo"))
        s = r["Supervisor"] or "Sin asignar"
        sums[s] = sums.get(s, 0.0) + minutos
        counts[s] = counts.get(s, 0) + 1
        enriched.append({**r, "_retardo_min": minutos})

    enriched.sort(key=lambda r: r["_retardo_min"], reverse=True)

    avg_by_supervisor = sorted(
        [
            {"supervisor": s, "avg_min": round(sums[s] / counts[s], 1)}
            for s in sums
        ],
        key=lambda x: x["avg_min"], reverse=True,
    )

    return {
        "total": len(latecomers),
        "list": [
            {
                "Nombre": r["Nombre"],
                "Supervisor": r["Supervisor"],
                "Hora_Programada": r["Hora_Programada"],
                "Hora_Inicio": r["Hora_Inicio"],
                "Tiempo_Retardo": r["Tiempo_Retardo"],
                "Tiempo_Retardo_Min": round(r["_retardo_min"], 1),
            }
            for r in enriched
        ],
        "avg_by_supervisor": avg_by_supervisor,
    }


def get_filter_options() -> dict:
    data = get_raw_data()
    return {
        "supervisors": sorted({r["Supervisor"] for r in data if r["Supervisor"]}),
        "campanas":    sorted({r["Campana"]    for r in data if r["Campana"]}),
        "estados":     ["Asistio", "Ausente", "Retardo"],
    }


def get_full_dashboard(filters: dict | None = None) -> dict:
    """Carga todos los datos en una sola llamada para minimizar queries."""
    from datetime import datetime
    data = get_raw_data(filters)
    return {
        "kpis":        get_kpis(data),
        "supervisors": get_supervisor_summary(data),
        "attendance":  data,
        "timeline":    get_timeline(data),
        "ausentismo":  get_ausentismo(data),
        "retardos":    get_retardos_detalle(data),
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_records": len(data),
    }
