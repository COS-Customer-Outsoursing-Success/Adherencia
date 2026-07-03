from __future__ import annotations

import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor

from config import Config

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.SimpleConnectionPool | None = None


def _create_pool() -> psycopg2.pool.SimpleConnectionPool:
    return psycopg2.pool.SimpleConnectionPool(
        1,
        5,
        host=Config.SUPABASE_DB_HOST,
        port=Config.SUPABASE_DB_PORT,
        dbname=Config.SUPABASE_DB_NAME,
        user=Config.SUPABASE_DB_USER,
        password=Config.SUPABASE_DB_PASSWORD,
        connect_timeout=15,
        sslmode="require",
    )


def get_pool() -> psycopg2.pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = _create_pool()
        logger.info("Pool de conexiones Supabase/Postgres creado")
    return _pool


@contextmanager
def get_cursor():
    """Context manager que entrega un cursor dict y devuelve la conexión al pool al salir."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def execute_query(query: str, params: tuple = ()) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(query, params)
        if cur.description is None:
            return []
        return cur.fetchall()


def execute_write(query: str, params: tuple = ()) -> None:
    with get_cursor() as cur:
        cur.execute(query, params)


def check_connection() -> dict:
    """Verifica la conectividad con Supabase. Devuelve {'ok': bool, 'detail': str}."""
    try:
        execute_query("SELECT 1 AS ping")
        return {"ok": True, "detail": "Conexión exitosa"}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}
