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
