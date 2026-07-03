import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Base de datos MySQL (origen, solo usada por el script de sync) ──────
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_DATABASE = os.getenv("DB_DATABASE", "")
    DB_USERNAME = os.getenv("DB_USERNAME", "")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    # ── Supabase / Postgres (destino, usada por la app Flask) ───────────────
    SUPABASE_DB_HOST = os.getenv("SUPABASE_DB_HOST", "")
    SUPABASE_DB_PORT = int(os.getenv("SUPABASE_DB_PORT", "5432"))
    SUPABASE_DB_NAME = os.getenv("SUPABASE_DB_NAME", "postgres")
    SUPABASE_DB_USER = os.getenv("SUPABASE_DB_USER", "postgres")
    SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")

    # ── Aplicación ─────────────────────────────────────────────────────────
    HOST = os.getenv("APP_HOST", "0.0.0.0")
    PORT = int(os.getenv("APP_PORT", "5000"))
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-change-me")
