"""Consultas SQL compartidas entre módulos de servicio (evita duplicar la query gigante)."""

# ── Lectura desde Supabase (usada por excesos.py y detalle_agente.py en la app desplegada) ──
AGENT_METRICS_SNAPSHOT_SQL = """
SELECT
    nombre                      AS "Nombres_Apellidos",
    supervisor                  AS "Supervisor",
    campana                     AS "Campana",
    llamadas                    AS "llamadas",
    cant_mrc_inb                AS "Cant_Mrc_Inb",
    cant_mrc_out                AS "Cant_Mrc_Out",
    ventas_inb                  AS "Ventas_Inb",
    ventas_out                  AS "Ventas_Out",
    t_login                     AS "T_login",
    t_dispo                     AS "T_dispo",
    t_dead                      AS "T_dead",
    t_preturno                  AS "T_preturno",
    t_capacitacion               AS "T_capacitacion",
    t_whatsapp                  AS "T_whatsapp",
    t_exceso_alm                AS "T_Exceso_Alm",
    t_exceso_break               AS "T_Exceso_Break",
    t_exceso_bano                AS "T_Exceso_Bano",
    t_logueado                  AS "T_logueado",
    aht                         AS "Aht",
    t_acw                       AS "T_acw",
    t_espera                    AS "T_espera",
    t_pausa_productiva            AS "T_pausa_productiva",
    cantidad_desconexiones       AS "cantidad_desconexiones",
    tiempo_desconexion_minutos    AS "tiempo_desconexion_minutos",
    porc_pausa                  AS "Porc_pausa",
    ocupacion                   AS "Ocupacion",
    disponibilidad               AS "Disponibilidad",
    utilizacion                 AS "Utilizacion",
    shrinkage                   AS "Shrinkage",
    eficiencia                  AS "Eficiencia"
FROM agent_metrics_snapshot
"""


# ── Lectura desde MySQL corporativo (usada solo por sync_to_supabase.py) ──
AGENT_METRICS_SQL = """
WITH base_login_logout AS (
    SELECT
        user,
        event,
        event_date,
        fecha
    FROM bbdd_bigdata_login_logout_vicidial.tb_login_logout_vicidial_fidelizacion
    WHERE event IN ('LOGIN', 'LOGOUT')
      AND fecha = CURDATE()

    UNION ALL

    SELECT
        user,
        event,
        event_date,
        fecha
    FROM bbdd_bigdata_login_logout_vicidial.tb_login_logout_vicidial_claro_terminales_tecnologia
    WHERE event IN ('LOGIN', 'LOGOUT')
      AND fecha = CURDATE()

    UNION ALL

    SELECT
        user,
        event,
        event_date,
        fecha
    FROM bbdd_bigdata_login_logout_vicidial.tb_login_logout_vicidial_tmk_bog
    WHERE event IN ('LOGIN', 'LOGOUT')
      AND fecha = CURDATE()
),

login_logout AS (
    SELECT
        user,
        event,
        event_date,
        fecha,
        LEAD(event) OVER (
            PARTITION BY user, fecha
            ORDER BY event_date
        ) AS next_event,
        LEAD(event_date) OVER (
            PARTITION BY user, fecha
            ORDER BY event_date
        ) AS next_event_date
    FROM base_login_logout
),

desconexiones AS (
    SELECT
        user,
        fecha,
        COUNT(*) AS cantidad_desconexiones,
        SUM(
            CASE
                WHEN event = 'LOGOUT'
                 AND next_event = 'LOGIN'
                 AND next_event_date > event_date
                THEN TIMESTAMPDIFF(SECOND, event_date, next_event_date)
                ELSE 0
            END
        ) / 86400 AS tiempo_desconexion_minutos
    FROM login_logout
    GROUP BY user, fecha
),

mrc_inbound AS (
    SELECT user AS Documento,
           COUNT(*) AS Cant_Mrc_Inb,
           SUM(CASE WHEN (status_name LIKE '%Venta%' OR status_name LIKE '%Fideliza%')
           AND status_name NOT LIKE '%No Venta%' THEN 1 ELSE 0 END) AS Ventas_Inb
    FROM (
        SELECT user COLLATE utf8mb4_unicode_ci AS user,
               call_date,
               status_name COLLATE utf8mb4_unicode_ci AS status_name
        FROM bbdd_bigdata_marcaciones_vicidial.tb_marcaciones_vicidial_inb_claro_terminales_tecnologia
        WHERE call_date >= CURDATE()

        UNION ALL

        SELECT user COLLATE utf8mb4_unicode_ci AS user,
               call_date,
               status_name COLLATE utf8mb4_unicode_ci AS status_name
        FROM bbdd_bigdata_marcaciones_vicidial.tb_marcaciones_vicidial_inb_fideliza_movil
        WHERE call_date >= CURDATE()

        UNION ALL

        SELECT user COLLATE utf8mb4_unicode_ci AS user,
               call_date,
               status_name COLLATE utf8mb4_unicode_ci AS status_name
        FROM bbdd_bigdata_marcaciones_vicidial.tb_marcaciones_vicidial_inb_tmk_bog
        WHERE call_date >= CURDATE()
    ) AS union_inb
    WHERE user <> 'VDCL'
    GROUP BY Documento
),

mrc_outbound AS (
    SELECT user AS Documento,
           COUNT(*) AS Cant_Mrc_Out,
           SUM(CASE WHEN (status_name LIKE '%Venta%' OR status_name LIKE '%Fideliza%')
           AND status_name NOT LIKE '%No Venta%' THEN 1 ELSE 0 END) AS Ventas_Out
    FROM (
        SELECT user COLLATE utf8mb4_unicode_ci AS user,
               call_date,
               status_name COLLATE utf8mb4_unicode_ci AS status_name
        FROM bbdd_bigdata_marcaciones_vicidial.tb_marcaciones_vicidial_out_claro_terminales_tecnologia
        WHERE call_date >= CURDATE()

        UNION ALL

        SELECT user COLLATE utf8mb4_unicode_ci AS user,
               call_date,
               status_name COLLATE utf8mb4_unicode_ci AS status_name
        FROM bbdd_bigdata_marcaciones_vicidial.tb_marcaciones_vicidial_out_fidelizacion
        WHERE call_date >= CURDATE()

        UNION ALL

        SELECT user COLLATE utf8mb4_unicode_ci AS user,
               call_date,
               status_name COLLATE utf8mb4_unicode_ci AS status_name
        FROM bbdd_bigdata_marcaciones_vicidial.tb_marcaciones_vicidial_out_tmk_bog
        WHERE call_date >= CURDATE()
    ) AS union_out
    WHERE user <> 'VDCL'
    GROUP BY Documento
)

SELECT
    DEA.cedula,
    DEA.usuario,
    IFNULL(HC.Nombres_Apellidos, DEA.usuario) AS Nombres_Apellidos,
    IFNULL(HC.Nombre_Supervisor, 'Sin Supervisor') AS Supervisor,
    IFNULL(HC.Campana, 'Sin Campana') AS Campana,
    IFNULL(HC.Servicio, 'Sin Servicio') AS Servicio,
    DEA.Conectado,
    DEA.llamadas,
    IFNULL(mrc_inb.Cant_Mrc_Inb, 0) AS Cant_Mrc_Inb,
    IFNULL(mrc_out.Cant_Mrc_Out, 0) AS Cant_Mrc_Out,
    IFNULL(mrc_inb.Ventas_Inb, 0) AS Ventas_Inb,
    IFNULL(mrc_out.Ventas_Out, 0) AS Ventas_Out,
    DEA.T_logueado/86400 AS T_logueado,
    DEA.T_espera/86400 AS T_espera,
    DEA.T_charla/86400 AS T_charla,
    DEA.T_dispo/86400 AS T_dispo,
    DEA.T_pausa/86400 AS T_pausa,
    DEA.T_dead/86400 AS T_dead,
    DEA.T_acd/86400 AS T_acd,
    DEA.T_conectado/86400 AS T_conectado,
    DEA.T_bano/86400 AS T_bano,
    DEA.T_almuerzo/86400 AS T_almuerzo,
    DEA.t_fallt/86400 AS t_fallt,
    DEA.T_break/86400 AS T_break,
    DEA.T_back/86400 AS T_back,
    DEA.T_acw/86400 AS T_acw,
    DEA.T_login/86400 AS T_login,
    DEA.T_capacitacion/86400 AS T_capacitacion,
    DEA.T_preturno/86400 AS T_preturno,
    DEA.T_pausa_activa/86400 AS T_pausa_activa,
    DEA.T_pausa_productiva/86400 AS T_pausa_productiva,
    DEA.T_chat/86400 AS T_chat,
    DEA.T_venta/86400 AS T_venta,
    DEA.T_coach/86400 AS T_coach,
    DEA.T_feedback/86400 AS T_feedback,
    DEA.T_email/86400 AS T_email,
    DEA.T_lagged/86400 AS T_lagged,
    DEA.T_llms/86400 AS T_llms,
    DEA.T_visible_vcdl/86400 AS T_visible_vcdl,
    DEA.T_hidden_vcdl/86400 AS T_hidden_vcdl,
    DEA.T_video_llamada/86400 AS T_video_llamada,
    DEA.T_whatsapp/86400 AS T_whatsapp,
    DEA.Aht,
    DEA.Eficiencia,
    DEA.Eficiencia_general,
    DEA.Porc_pausa,
    DEA.Ocupacion,
    DEA.Ocupacion_general,
    DEA.Disponibilidad,
    DEA.Disponibilidad_general,
    DEA.Utilizacion,
    DEA.Utilizacion_general,
    DEA.Shrinkage,
    DEA.Shrinkage_general,
    DEA.Fecha,
    SOUL.T_Programado_Turno/86400 AS T_Programado_Turno,
    SOUL.T_Programado_PausaAc/86400 AS T_Programado_PausaAc,
    SOUL.T_Programado_Almuerzo/86400 AS T_Programado_Almuerzo,
    SOUL.T_Programado_Break/86400 AS T_Programado_Break,
    SOUL.T_Programado_Bano/86400 AS T_Programado_Bano,
    IFNULL(dex.cantidad_desconexiones, 0) AS cantidad_desconexiones,
    IFNULL(dex.tiempo_desconexion_minutos, 0) AS tiempo_desconexion_minutos,
    ROUND(
        ((T_logueado - (
            IF(T_pausa_activa > SOUL.T_Programado_PausaAc, T_pausa_activa - SOUL.T_Programado_PausaAc, 0) +
            IF(T_almuerzo > SOUL.T_Programado_Almuerzo, T_almuerzo - SOUL.T_Programado_Almuerzo, 0) +
            IF(T_break > SOUL.T_Programado_Break, T_break - SOUL.T_Programado_Break, 0) +
            IF(T_bano > SOUL.T_Programado_Bano, T_bano - SOUL.T_Programado_Bano, 0)
        )) / NULLIF(SOUL.T_Programado_Turno, 0)) * 100, 2
    ) AS Conexion_Porcen,
    CASE WHEN DEA.T_almuerzo > SOUL.T_Programado_Almuerzo
    THEN (DEA.T_almuerzo - SOUL.T_Programado_Almuerzo)/86400 ELSE 0
    END AS T_Exceso_Alm,
    CASE WHEN DEA.T_break > 1200
    THEN (DEA.T_break - 1200)/86400 ELSE 0
    END AS  T_Exceso_Break,
    CASE WHEN DEA.T_bano > 900
    THEN (DEA.T_bano - 900)/86400 ELSE 0
    END AS T_Exceso_Bano
FROM
    (
 SELECT
        cedula,
        usuario,
            IF(cedula > 0, 1, 0) AS Conectado,
        llamadas,
        T_logueado,
        T_espera,
        T_charla,
        T_dispo,
        T_pausa,
        T_dead,
        T_acd,
        T_conectado,
        t_fallt,
        T_back,
        T_acw,
        T_login,
        T_capacitacion,
        T_preturno,
        T_pausa_productiva,
        T_chat,
        T_venta,
        T_coach,
        T_feedback,
        T_email,
        T_lagged,
        T_llms,
        T_visible_vcdl,
        T_hidden_vcdl,
        T_video_llamada,
        T_whatsapp,
            IFNULL(((T_acw + T_acd) / NULLIF(llamadas, 0) / 86400), 0) AS Aht,
            IFNULL((T_dispo + T_acd) / NULLIF(T_logueado, 0), 0) AS Eficiencia,
            IFNULL((T_dispo + T_acd + T_video_llamada + T_whatsapp + T_chat + T_pausa_productiva) / NULLIF(T_logueado, 0), 0) AS Eficiencia_general,
            IFNULL((T_pausa) / NULLIF(T_logueado, 0), 0) AS Porc_pausa,
            IFNULL((T_acw + T_acd) / NULLIF(T_acw + T_acd + T_espera, 0), 0) AS Ocupacion,
            IFNULL((T_acw + T_acd + T_video_llamada + T_whatsapp + T_chat + T_pausa_productiva) / NULLIF(T_acw + T_acd + T_video_llamada + T_whatsapp + T_chat + T_pausa_productiva + T_espera, 0), 0) AS Ocupacion_general,
            IFNULL((T_espera) / NULLIF(T_acw + T_acd + T_espera, 0), 0) AS Disponibilidad,
            IFNULL((T_espera) / NULLIF(T_acw + T_acd + T_video_llamada + T_whatsapp + T_chat + T_pausa_productiva + T_espera, 0), 0) AS Disponibilidad_general,
            IFNULL((T_espera + T_acw + T_acd + IFNULL(T_pausa_productiva, 0)) / NULLIF(T_logueado, 0), 0) AS Utilizacion,
            IFNULL((T_espera + T_acw + T_acd + IFNULL(T_video_llamada,0) + IFNULL(T_whatsapp,0) + IFNULL(T_chat,0) + IFNULL(T_pausa_productiva, 0)) / NULLIF(T_logueado, 0), 0) AS Utilizacion_general,
            1 - IFNULL((T_espera + T_acw + T_acd + IFNULL(T_pausa_productiva, 0)) / NULLIF(T_logueado, 0), 0) AS Shrinkage,
            1- IFNULL((T_espera + T_acw + T_acd + IFNULL(T_video_llamada,0) + IFNULL(T_whatsapp,0) + IFNULL(T_chat,0) + IFNULL(T_pausa_productiva, 0)) / NULLIF(T_logueado, 0), 0) AS Shrinkage_general,
            T_bano,
            T_break,
            T_almuerzo,
            T_pausa_activa,
            Fecha
        FROM
            (SELECT
                identificacion AS cedula,
                usuario,
                llamadas,
                TIME_TO_SEC(t_login_time) AS T_logueado,
                TIME_TO_SEC(t_espera) AS T_espera,
                TIME_TO_SEC(t_charla) AS T_charla,
                TIME_TO_SEC(t_dispo) AS T_dispo,
                TIME_TO_SEC(t_pausa) AS T_pausa,
                TIME_TO_SEC(t_llamada_muerta) AS T_dead,
                TIME_TO_SEC(t_customer) AS T_acd,
                TIME_TO_SEC(t_connected) AS T_conectado,
                TIME_TO_SEC(t_bano) AS T_bano,
                TIME_TO_SEC(t_break) AS T_break,
                TIME_TO_SEC(t_almuerzo) AS T_almuerzo,
                TIME_TO_SEC(t_fallt) AS t_fallt,
                TIME_TO_SEC(t_back) AS T_back,
                TIME_TO_SEC(t_pausa_productiva) AS T_pausa_productiva,
                TIME_TO_SEC(t_llamada_muerta) + TIME_TO_SEC(t_dispo) AS T_acw,
                TIME_TO_SEC(t_login) AS T_login,
                TIME_TO_SEC(t_pausa_activa) AS T_pausa_activa,
                TIME_TO_SEC(t_capacitacion) AS T_capacitacion,
                TIME_TO_SEC(t_preturno) AS T_preturno,
                TIME_TO_SEC(t_chat) AS T_chat,
                TIME_TO_SEC(t_venta) AS T_venta,
                TIME_TO_SEC(t_coach) AS T_coach,
                TIME_TO_SEC(t_feedback) AS T_feedback,
                TIME_TO_SEC(t_email) AS T_email,
                TIME_TO_SEC(t_lagged) AS T_lagged,
                TIME_TO_SEC(t_llms) AS T_llms,
                TIME_TO_SEC(t_visible_vcdl) AS T_visible_vcdl,
                TIME_TO_SEC(t_hiiden_vcdl) AS T_hidden_vcdl,
                TIME_TO_SEC(t_video_llamada) AS T_video_llamada,
                TIME_TO_SEC(t_whatsapp) AS T_whatsapp,
                DATE(fecha_cargue) AS Fecha
             FROM bbdd_cs_bog_tmk.tb_detalle_agente_daily_new_dts
             WHERE fecha_cargue >= curdate()
             AND usuario <> 'TOTALS'
            ) AS SB
    ) DEA
LEFT JOIN (SELECT
        Documento, Nombres_Apellidos, Nombre_Supervisor, Campana, Servicio
    FROM
        bbdd_config.tb_headcount
    WHERE
        Campana IN ('Claro - Movil Tmk Bogota', 'Claro / Hogar Tmk Bogota', 'Claro - Terminales & Tecnologia Bogota', 'Claro - Hogar Tmk Bogota')
            AND estado = 'Activo') HC
            ON DEA.cedula = HC.Documento
    LEFT JOIN (
    SELECT
        documento,
        TIME_TO_SEC(TIMEDIFF(hora_prog_fin_turn, hora_prog_ini_turn)) AS T_Programado_Turno,
        TIME_TO_SEC(TIMEDIFF(hora_prog_fin_pausa, hora_prog_ini_pausa)) AS T_Programado_PausaAc,
        TIME_TO_SEC(TIMEDIFF(hora_prog_fin_almuerzo, hora_prog_ini_almuerzo)) AS T_Programado_Almuerzo,
        TIME_TO_SEC(TIMEDIFF(hora_prog_fin_break_2, hora_prog_ini_break_2)) AS T_Programado_Break,
        TIME_TO_SEC(TIMEDIFF(hora_prog_fin_baño, hora_prog_ini_baño)) AS T_Programado_Bano
    FROM
        bbdd_config.tb_soul_proglog
    WHERE
        fecha_prog_ini_turn = curdate()) SOUL
        ON DEA.cedula = SOUL.documento
LEFT JOIN mrc_inbound AS mrc_inb ON DEA.cedula = mrc_inb.Documento
LEFT JOIN mrc_outbound AS mrc_out ON DEA.cedula = mrc_out.Documento
LEFT JOIN desconexiones AS dex ON DEA.cedula = dex.user
"""
