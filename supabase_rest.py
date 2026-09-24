"""Escritura hacia Supabase vía su API REST (PostgREST) sobre HTTPS puerto 443.

Se usa exclusivamente en sync_to_supabase.py como alternativa a la conexión
directa por Postgres (puertos 5432/6543), que la red corporativa bloquea.
La app Flask desplegada sigue leyendo por conexión directa (supabase_db.py),
ya que Vercel no tiene esa restricción de puertos.
"""
from __future__ import annotations

import logging
from decimal import Decimal

import truststore

truststore.inject_into_ssl()  # usa el almacén de certificados de Windows (confía en el
                               # proxy TLS corporativo), en vez del bundle interno de requests

import requests

from config import Config

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500


def _headers() -> dict:
    return {
        "apikey": Config.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {Config.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def delete_all(table: str) -> None:
    url = f"{Config.SUPABASE_URL}/rest/v1/{table}"
    resp = requests.delete(url, headers=_headers(), params={"id": "gt.0"}, timeout=30)
    resp.raise_for_status()


def delete_by_date(table: str, fecha: str) -> None:
    url = f"{Config.SUPABASE_URL}/rest/v1/{table}"
    resp = requests.delete(url, headers=_headers(), params={"fecha": f"eq.{fecha}"}, timeout=30)
    resp.raise_for_status()


def _jsonable(value):
    """Convierte tipos no serializables por json (Decimal de MySQL, etc.) a nativos de Python."""
    if isinstance(value, Decimal):
        return float(value)
    return value


def _sanitize_rows(rows: list[dict]) -> list[dict]:
    return [{k: _jsonable(v) for k, v in row.items()} for row in rows]


def bulk_insert(table: str, rows: list[dict]) -> None:
    if not rows:
        return
    rows = _sanitize_rows(rows)
    url = f"{Config.SUPABASE_URL}/rest/v1/{table}"
    for i in range(0, len(rows), _BATCH_SIZE):
        batch = rows[i:i + _BATCH_SIZE]
        resp = requests.post(url, headers=_headers(), json=batch, timeout=60)
        resp.raise_for_status()


def replace_all(table: str, rows: list[dict]) -> None:
    """Borra todo el contenido de la tabla y lo reemplaza por `rows`."""
    delete_all(table)
    bulk_insert(table, rows)


def replace_by_date(table: str, fecha: str, rows: list[dict]) -> None:
    """Borra solo las filas de `fecha` y las reemplaza por `rows`, preservando
    el histórico de otras fechas (usado por el sync incremental diario)."""
    delete_by_date(table, fecha)
    bulk_insert(table, rows)


def fetch_attendance(fecha_inicio: str, fecha_fin: str) -> list[dict]:
    """Obtiene los datos de asistencia usando la API REST para evitar
    el bloqueo de puertos de la conexión directa a Postgres."""
    url = f"{Config.SUPABASE_URL}/rest/v1/attendance_snapshot"
    headers = _headers()
    # Para GET, no queremos return=minimal
    if "Prefer" in headers:
        del headers["Prefer"]
        
    params = [
        ("select", "Fecha:fecha,Cedula:cedula,Nombre:nombre,Supervisor:supervisor,Campana:campana,Asiste:asiste,Ausente:ausente,Retardo:retardo,Hora_Programada:hora_programada,Hora_Inicio:hora_inicio,Tiempo_Retardo:tiempo_retardo"),
        ("fecha", f"gte.{fecha_inicio}"),
        ("fecha", f"lte.{fecha_fin}")
    ]
    
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_agent_metrics(fecha_inicio: str, fecha_fin: str) -> list[dict]:
    """Obtiene los datos de métricas de agente usando la API REST."""
    url = f"{Config.SUPABASE_URL}/rest/v1/agent_metrics_snapshot"
    headers = _headers()
    if "Prefer" in headers:
        del headers["Prefer"]
        
    cols = [
        "Fecha:fecha",
        "Nombres_Apellidos:nombre",
        "Supervisor:supervisor",
        "Campana:campana",
        "llamadas:llamadas",
        "Cant_Mrc_Inb:cant_mrc_inb",
        "Cant_Mrc_Out:cant_mrc_out",
        "Ventas_Inb:ventas_inb",
        "Ventas_Out:ventas_out",
        "T_login:t_login",
        "T_dispo:t_dispo",
        "T_dead:t_dead",
        "T_preturno:t_preturno",
        "T_capacitacion:t_capacitacion",
        "T_whatsapp:t_whatsapp",
        "T_Exceso_Alm:t_exceso_alm",
        "T_Exceso_Break:t_exceso_break",
        "T_Exceso_Bano:t_exceso_bano",
        "T_logueado:t_logueado",
        "Aht:aht",
        "T_acw:t_acw",
        "T_espera:t_espera",
        "T_pausa_productiva:t_pausa_productiva",
        "cantidad_desconexiones:cantidad_desconexiones",
        "tiempo_desconexion_minutos:tiempo_desconexion_minutos",
        "Porc_pausa:porc_pausa",
        "Ocupacion:ocupacion",
        "Disponibilidad:disponibilidad",
        "Utilizacion:utilizacion",
        "Shrinkage:shrinkage",
        "Eficiencia:eficiencia"
    ]
    
    params = [
        ("select", ",".join(cols)),
        ("fecha", f"gte.{fecha_inicio}"),
        ("fecha", f"lte.{fecha_fin}")
    ]
    
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()
