-- Agrega la cédula del asesor al snapshot de asistencia (Retardos-Ausentismo).
-- Aplicar una sola vez en el SQL Editor de Supabase.

ALTER TABLE attendance_snapshot ADD COLUMN IF NOT EXISTS cedula TEXT;
