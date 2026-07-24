# Claro Ventas — Dashboard de Asistencia y Desempeño

Suite de dashboards ejecutivos para el monitoreo en tiempo real de **asistencia**, **excesos de pausas** y **desempeño individual** de los asesores de call center de **Claro Ventas** (Bogotá).

Backend Flask (Python) + Supabase (Postgres) como base de lectura, frontend HTML/CSS/JS con Chart.js. Los datos reales viven en un MySQL corporativo interno; un script separado los sincroniza periódicamente hacia Supabase, que es lo que la app desplegada realmente consulta.

---

## 1. Visión general

El proyecto tiene **tres paneles**, cada uno con su propia página, ruta API y lógica de negocio:

| Panel | URL | Para qué sirve |
|---|---|---|
| **Asistencia** | `/` | ¿Quién llegó a tiempo, quién faltó, quién llegó tarde hoy? |
| **Excesos** | `/excesos` | ¿Quién se excedió en tiempos de almuerzo, break o baño? |
| **Detalle de Agente** | `/detalle-agente` | Ficha de desempeño por asesor: llamadas, ventas, tiempos, ocupación, eficiencia. |

Los tres se alimentan de datos que **ya vienen calculados** desde consultas SQL pesadas sobre los sistemas del call center (Vicidial, headcount, programación de turnos, etc.). El dashboard en sí no hace cálculos de negocio complejos: agrega, filtra y presenta lo que ya llega resuelto desde la base de datos.

---

## 2. Arquitectura: por qué hay dos bases de datos

```
┌─────────────────────────┐        sync_to_supabase.py        ┌───────────────────────┐        lectura directa        ┌──────────────────┐
│   MySQL corporativo     │ ───────────(cada X minutos)─────▶ │  Supabase (Postgres)  │ ◀────────(psycopg2)────────── │  App Flask        │
│   (red interna Claro)   │   vía API REST de Supabase (443)   │  attendance_snapshot  │                                │  (desplegada en   │
│   Vicidial, headcount,  │                                     │  agent_metrics_snapshot│                               │  Vercel)          │
│   programación de turno │                                     └───────────────────────┘                                └──────────────────┘
└─────────────────────────┘
```

**El problema que resuelve esta arquitectura:** la app desplegada (en Vercel) necesita ser accesible desde internet, pero el MySQL corporativo vive dentro de la red interna de Claro y no es alcanzable desde afuera. Al mismo tiempo, la red corporativa bloquea los puertos directos de Postgres (5432/6543) hacia Supabase, así que un equipo dentro de la red no puede escribir directo a Supabase por conexión de base de datos.

La solución:

1. **`sync_to_supabase.py`** corre en una máquina *dentro* de la red corporativa (con acceso al MySQL interno). Este script:
   - Lee de MySQL con conexión directa (`database.py`, puerto 3306).
   - Escribe en Supabase usando su **API REST/PostgREST sobre HTTPS puerto 443** (`supabase_rest.py`), que nunca está bloqueado.
   - Se ejecuta periódicamente mediante el **Programador de tareas de Windows**, invocando `run_sync.bat`.
2. **La app Flask desplegada** (`app.py` / `wsgi.py` / `api/index.py` en Vercel) **nunca se conecta al MySQL corporativo**. Solo lee de Supabase por conexión directa a Postgres (`supabase_db.py`), porque Vercel sí tiene salida libre por esos puertos.

Se sincronizan dos tablas/instantáneas independientes:

| Tabla en Supabase | Alimenta a | Se llena desde |
|---|---|---|
| `attendance_snapshot` | Panel de Asistencia | Query de asistencia (`services/attendance.py::get_raw_data_from_mysql`) |
| `agent_metrics_snapshot` | Excesos y Detalle de Agente | Query gigante de métricas (`services/_queries.py::AGENT_METRICS_SQL`) |

Cada sincronización **reemplaza el contenido completo** de la tabla destino (borra todo e inserta de nuevo — `supabase_rest.replace_all`), por lo que el dashboard siempre refleja la última foto tomada del MySQL, nunca datos acumulados históricamente.

---

## 3. Estructura del proyecto

```
claro-asistencia/
├── app.py                     # Fábrica de la app Flask (create_app), bloqueo de móviles
├── wsgi.py                    # Punto de entrada para servidores de producción (gunicorn/waitress)
├── api/index.py               # Punto de entrada específico para Vercel (serverless)
├── config.py                  # Config centralizada, lee variables de entorno (.env)
├── database.py                # Pool de conexiones MySQL (mysql-connector), solo usado por el sync
├── supabase_db.py             # Pool de conexiones Postgres directo a Supabase (usado por la app Flask)
├── supabase_rest.py           # Cliente REST/PostgREST de Supabase (usado solo por el sync, vía HTTPS 443)
├── sync_to_supabase.py        # Script que copia MySQL → Supabase (attendance + agent_metrics)
├── run_sync.bat               # Batch para invocar el sync desde el Programador de tareas de Windows
├── sync_log.txt               # Log acumulado de cada corrida del sync
├── vercel.json                # Configuración de despliegue serverless en Vercel
├── requirements.txt           # Dependencias Python
├── .env / .env.example        # Variables de entorno (el real NO se sube a git)
├── routes/
│   ├── __init__.py            # Registra los 3 blueprints en la app
│   ├── api.py                 # Rutas de "/" y /api/* → panel de Asistencia
│   ├── excesos.py              # Rutas de /excesos y /api/excesos*
│   └── detalle_agente.py       # Rutas de /detalle-agente y /api/detalle-agente*
├── services/
│   ├── attendance.py           # Lógica de negocio: asistencia, ausentismo, retardos, timeline
│   ├── excesos.py               # Lógica de negocio: excesos de almuerzo/break/baño
│   ├── detalle_agente.py        # Lógica de negocio: métricas de desempeño por agente
│   └── _queries.py              # SQL compartido (queries gigantes usadas por el sync y por Supabase)
├── utils/
│   ├── formatters.py            # Conversión de tipos (timedelta→string, segundos→HH:MM:SS, %)
│   └── device_guard.py           # Bloquea el acceso desde navegadores móviles
├── templates/
│   ├── index.html               # Vista del panel de Asistencia
│   ├── excesos.html              # Vista del panel de Excesos
│   └── detalle_agente.html       # Vista del panel de Detalle de Agente
└── static/
    ├── css/dashboard.css         # Estilos (compartidos por los 3 paneles)
    ├── js/dashboard.js            # Lógica frontend del panel de Asistencia
    ├── js/excesos.js               # Lógica frontend del panel de Excesos
    ├── js/detalle_agente.js        # Lógica frontend del panel de Detalle de Agente
    └── img/
```

---

## 4. Requisitos

| Componente | Versión mínima |
|---|---|
| Python | 3.8+ (recomendado 3.12) |
| Cuenta Supabase | proyecto Postgres activo |
| Acceso al MySQL corporativo | solo necesario en la máquina que corre el sync |
| pip | 23+ |

---

## 5. Instalación

```bash
# 1. Clonar / copiar el proyecto
cd C:\ruta\donde\quieres\el\proyecto

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/macOS

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
copy .env.example .env         # y editar con los valores reales
```

### Variables de entorno (`.env`)

| Variable | Usada por | Descripción |
|---|---|---|
| `DB_HOST`, `DB_PORT`, `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD` | `sync_to_supabase.py` | Conexión directa al MySQL corporativo (origen de datos). |
| `SUPABASE_DB_HOST`, `SUPABASE_DB_PORT`, `SUPABASE_DB_NAME`, `SUPABASE_DB_USER`, `SUPABASE_DB_PASSWORD` | App Flask (`supabase_db.py`) | Conexión directa Postgres a Supabase, para **leer** los snapshots. |
| `SUPABASE_PROJECT_REF`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | `sync_to_supabase.py` (`supabase_rest.py`) | Credenciales de la API REST de Supabase, para **escribir** los snapshots cuando el puerto Postgres directo está bloqueado. |
| `APP_HOST`, `APP_PORT`, `DEBUG`, `SECRET_KEY` | App Flask | Configuración del servidor web. |
| `EXCESOS_MOCK` | `services/excesos.py`, `services/detalle_agente.py` | Si vale `1`, usa datos ficticios generados en memoria en vez de consultar Supabase (útil para previsualizar la interfaz sin datos reales). |

> **Seguridad:** nunca subir `.env` a un repositorio público. El `SUPABASE_SERVICE_ROLE_KEY` tiene permisos administrativos totales sobre la base de datos.

---

## 6. Ejecución

### Desarrollo local (panel web)

```bash
python app.py
# Abrir http://localhost:5000
```

### Sincronización de datos (MySQL → Supabase)

Debe ejecutarse **en una máquina con acceso directo al MySQL corporativo**, no en el servidor donde vive la app web.

```bash
python sync_to_supabase.py
```

En producción se programa con el **Programador de tareas de Windows** apuntando a `run_sync.bat`, que ejecuta el script y anexa la salida a `sync_log.txt`. Se recomienda correrlo cada 5–15 minutos.

### Producción (panel web)

- **Vercel (actual):** el despliegue serverless usa `vercel.json` + `api/index.py`. Cada request instancia la app Flask; no requiere servidor propio.
- **Windows — Waitress:**
  ```bash
  pip install waitress
  waitress-serve --host=0.0.0.0 --port=5000 wsgi:application
  ```
- **Linux — Gunicorn / systemd:**
  ```bash
  pip install gunicorn
  gunicorn -w 4 -b 0.0.0.0:5000 wsgi:application
  ```

---

## 7. API REST

### Panel de Asistencia (`routes/api.py`)

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/` | Vista del dashboard de asistencia |
| GET | `/api/health` | Estado de la conexión a Supabase |
| GET | `/api/dashboard` | Todos los datos de asistencia en una sola llamada (KPIs + supervisores + timeline + ausentismo + retardos) |
| GET | `/api/kpis` | Solo los indicadores KPI |
| GET | `/api/supervisors` | Resumen agregado por supervisor |
| GET | `/api/attendance` | Detalle fila por fila de cada asesor |
| GET | `/api/timeline` | Llegadas agrupadas en intervalos de 30 minutos |
| GET | `/api/filters` | Valores disponibles para los filtros (supervisores, campañas) |

Filtros opcionales (query string): `?supervisor=`, `?campana=`, `?estado=Asistio|Ausente|Retardo`, `?hora_inicio=07:00&hora_fin=08:30`

### Panel de Excesos (`routes/excesos.py`)

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/excesos` | Vista del dashboard de excesos |
| GET | `/api/excesos` | KPIs + resumen por supervisor + detalle por agente |
| GET | `/api/excesos/filters` | Valores disponibles para los filtros |

Filtros: `?supervisor=`, `?campana=`, `?solo_con_exceso=1` (solo agentes con algún exceso)

### Panel de Detalle de Agente (`routes/detalle_agente.py`)

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/detalle-agente` | Vista del dashboard de detalle de agente |
| GET | `/api/detalle-agente` | KPIs + ficha de desempeño de cada agente |
| GET | `/api/detalle-agente/filters` | Valores disponibles para los filtros |

Filtros: `?supervisor=`, `?campana=`

---

## 8. Glosario de negocio

### Asistencia

- **Programado**: el asesor tenía turno asignado hoy.
- **Asiste**: hizo login en el sistema de marcación (Vicidial) hoy.
- **Ausente**: no hizo login y ya pasó la hora programada de inicio de turno.
- **Retardo**: hizo login más de 60 segundos después de la hora programada.
- **Puntual**: asistió sin retardo.
- Semáforo de ausentismo por supervisor: **verde** < 5%, **amarillo** 5–10%, **rojo** > 10%.

### Excesos

Se calcula cuánto se excedió cada asesor sobre el tiempo permitido en:
- **Almuerzo** (límite viene de la programación de turno de cada asesor, `T_Programado_Almuerzo`).
- **Break** (límite fijo: 1200 segundos = 20 minutos).
- **Baño** (límite fijo: 900 segundos = 15 minutos).

Solo se cuenta el tiempo por encima del límite (si no se excedió, el exceso es 0).

### Detalle de Agente (métricas de desempeño)

- **AHT** (Average Handling Time): tiempo promedio de manejo por llamada = (tiempo en llamada + tiempo de cierre) / número de llamadas.
- **ACW** (After Call Work): tiempo de cierre/documentación después de colgar.
- **T_dispo / Disponibilidad**: tiempo en espera de llamadas sobre el tiempo total en cola.
- **Ocupación**: proporción del tiempo "productivo" (hablando + cerrando) sobre el tiempo total disponible para atender.
- **Utilización**: similar a ocupación pero incluye también canales adicionales (chat, WhatsApp, videollamada, pausas productivas).
- **Shrinkage**: el complemento de la utilización — el tiempo que el agente estuvo logueado pero NO fue productivo.
- **Eficiencia**: proporción del tiempo logueado que se dedicó a atención real de clientes.
- **Cant_Desconex / T_Desconex**: cantidad y duración de desconexiones (logout seguido de login) detectadas durante el turno.

---

## 9. Seguridad y restricciones

- **Bloqueo de dispositivos móviles** (`utils/device_guard.py`): cualquier request cuyo `User-Agent` coincida con Android/iPhone/iPad/Mobile recibe una página de "no disponible" (HTTP 403). Es una restricción de uso (el dashboard está pensado para pantallas grandes/escritorio), no una medida de seguridad — el User-Agent se puede falsificar.
- El `SECRET_KEY` de Flask y el `SUPABASE_SERVICE_ROLE_KEY` deben mantenerse fuera de git (`.env` está en `.gitignore`).
- La app desplegada solo tiene permisos de **lectura** sobre Supabase; la escritura (sync) requiere el service role key y corre en una máquina controlada, no en el servidor público.

---

## 10. Resolución de problemas

| Error | Causa probable | Solución |
|---|---|---|
| `/api/health` responde `ok: false` | Supabase inaccesible o credenciales `SUPABASE_DB_*` incorrectas | Verificar `.env` y que el proyecto Supabase esté activo |
| Dashboard muestra `—` o listas vacías | El sync no ha corrido recientemente, o no hay agentes programados para hoy | Revisar `sync_log.txt`; correr `python sync_to_supabase.py` manualmente |
| `Can't connect to MySQL` (solo al correr el sync) | Credenciales incorrectas o sin red hacia el MySQL corporativo | Verificar `.env` (`DB_*`) y que el equipo tenga acceso a la red interna |
| Error 401/403 al sincronizar hacia Supabase | `SUPABASE_SERVICE_ROLE_KEY` inválido o expirado | Regenerar la key en el panel de Supabase y actualizar `.env` |
| `ModuleNotFoundError` | Entorno virtual no activado | Ejecutar `venv\Scripts\activate` |
| Gráficas no cargan | CDN de Chart.js/SheetJS bloqueado por la red | Descargar las librerías localmente (ver README original / `static/js`) y referenciarlas desde ahí |
| Panel de Excesos/Detalle de Agente vacío pero Asistencia funciona | `agent_metrics_snapshot` no se sincronizó (el sync de asistencia y de métricas son independientes y uno puede fallar sin afectar al otro) | Revisar `sync_log.txt` para el bloque `sync_agent_metrics` |
| Dashboard abierto desde el celular muestra "Contenido no disponible" | Comportamiento esperado — el panel está bloqueado en móviles | Abrir desde un computador de escritorio |
