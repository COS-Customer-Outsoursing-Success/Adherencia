from __future__ import annotations

import logging
from contextlib import contextmanager

import mysql.connector
from mysql.connector import Error, pooling

from config import Config

logger = logging.getLogger(__name__)

_pool: pooling.MySQLConnectionPool | None = None


def _create_pool() -> pooling.MySQLConnectionPool:
    return pooling.MySQLConnectionPool(
        pool_name="claro_pool",
        pool_size=5,
        pool_reset_session=True,
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        database=Config.DB_DATABASE,
        user=Config.DB_USERNAME,
        password=Config.DB_PASSWORD,
        autocommit=True,
        connection_timeout=30,
        use_pure=True,
    )


def get_pool() -> pooling.MySQLConnectionPool:
    global _pool
    if _pool is None:
        try:
            _pool = _create_pool()
            logger.info("Pool de conexiones MySQL creado (size=5)")
        except Error as exc:
            logger.critical("No se pudo crear el pool de conexiones: %s", exc)
            raise
    return _pool


@contextmanager
def get_cursor():
    """Context manager que entrega un cursor dict y cierra la conexión al salir."""
    conn = None
    cursor = None
    try:
        conn = get_pool().get_connection()
        cursor = conn.cursor(dictionary=True)
        yield cursor
    except Error as exc:
        logger.error("Error de base de datos: %s", exc)
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def execute_query(query: str, params: tuple = ()) -> list[dict]:
    with get_cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def check_connection() -> dict:
    """Verifica la conectividad con la BD. Devuelve {'ok': bool, 'detail': str}."""
    try:
        rows = execute_query("SELECT 1 AS ping")
        return {"ok": True, "detail": "Conexión exitosa"}
    except Exception as exc:
        return {"ok": False, "detail": str(exc)}
