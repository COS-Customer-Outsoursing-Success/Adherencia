-- Agrega histórico por día a los snapshots de Supabase.
-- Aplicar una sola vez (SQL Editor de Supabase, o vía supabase_db.execute_write
-- si el puerto 5432 no está bloqueado desde la máquina que lo ejecute).
--
-- Después de correr esto, sync_to_supabase.py pasa de reemplazar toda la tabla
-- en cada corrida a reemplazar solo las filas de la fecha sincronizada
-- (ver supabase_rest.replace_by_date), y backfill_month.py se usa una vez para
-- cargar los días ya transcurridos.

ALTER TABLE attendance_snapshot ADD COLUMN IF NOT EXISTS fecha DATE;
CREATE INDEX IF NOT EXISTS idx_attendance_snapshot_fecha ON attendance_snapshot (fecha);

ALTER TABLE agent_metrics_snapshot ADD COLUMN IF NOT EXISTS fecha DATE;
CREATE INDEX IF NOT EXISTS idx_agent_metrics_snapshot_fecha ON agent_metrics_snapshot (fecha);
