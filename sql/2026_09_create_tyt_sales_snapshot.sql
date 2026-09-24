-- Snapshot diario de ventas de Terminales & Tecnología por asesor (columnas TyT
-- de Detalle de Asesores). Aplicar una sola vez en el SQL Editor de Supabase.
--
-- sync_to_supabase.py lo llena día a día desde el MySQL corporativo
-- (tb_soul2_720_venta_de_terminales_y_tecnologia_bogota), ya que Vercel no
-- tiene acceso a ese servidor.

CREATE TABLE IF NOT EXISTS tyt_sales_snapshot (
    id                BIGSERIAL PRIMARY KEY,
    fecha             DATE NOT NULL,
    nombre            TEXT NOT NULL,
    terminales        INTEGER NOT NULL DEFAULT 0,
    tecnologia        INTEGER NOT NULL DEFAULT 0,
    unidades          INTEGER NOT NULL DEFAULT 0,
    dolar_terminales  NUMERIC(15, 2) NOT NULL DEFAULT 0,
    dolar_tecnologia  NUMERIC(15, 2) NOT NULL DEFAULT 0,
    dolar_total       NUMERIC(15, 2) NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_tyt_sales_snapshot_fecha ON tyt_sales_snapshot (fecha);

ALTER TABLE tyt_sales_snapshot ENABLE ROW LEVEL SECURITY;
GRANT ALL ON tyt_sales_snapshot TO service_role;
GRANT USAGE, SELECT ON SEQUENCE tyt_sales_snapshot_id_seq TO service_role;
