# Claro Ventas — Dashboard de Asistencia

Dashboard web ejecutivo para el monitoreo en tiempo real de la asistencia de asesores de **Claro Ventas** (Bogotá). Backend Flask + MySQL, frontend HTML/CSS/JS con Chart.js.

---

## Estructura del proyecto

```
claro-asistencia/
├── app.py                  # Punto de entrada Flask
├── wsgi.py                 # Punto de entrada para producción
├── config.py               # Configuración desde variables de entorno
├── database.py             # Pool de conexiones MySQL
├── requirements.txt        # Dependencias Python
├── .env                    # Variables de entorno (NO subir a git)
├── routes/
│   ├── __init__.py
│   └── api.py              # Rutas REST y vista principal
├── services/
│   ├── __init__.py
│   └── attendance.py       # Lógica de negocio y consultas
├── templates/
│   └── index.html          # Dashboard SPA
├── static/
│   ├── css/dashboard.css
│   ├── js/dashboard.js
│   └── img/
└── utils/
    ├── __init__.py
    └── formatters.py       # Helpers de serialización
```

---

## Requisitos

| Componente | Versión mínima |
|---|---|
| Python | 3.8+ (recomendado 3.10+) |
| MySQL  | 5.7+ / 8.x |
| pip    | 23+ |

---

## Instalación

### 1. Clonar / copiar el proyecto

```bash
# Windows PowerShell
cd C:\ruta\donde\quieres\el\proyecto
```

### 2. Crear entorno virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Edita el archivo `.env` con los datos reales de conexión:

```env
DB_HOST=192.168.1.100        # IP o hostname del servidor MySQL
DB_PORT=3306
DB_DATABASE=bbdd_config
DB_USERNAME=usuario_mysql
DB_PASSWORD=contraseña_mysql

APP_HOST=0.0.0.0
APP_PORT=5000
DEBUG=False
SECRET_KEY=genera-una-clave-aleatoria-segura
```

> **Seguridad:** nunca subas el archivo `.env` a repositorios públicos.

---

## Ejecución en desarrollo

```bash
# Con el entorno virtual activado
python app.py
```

Abrir en el navegador: `http://localhost:5000`

---

## Ejecución en producción

### Windows — Waitress (servidor WSGI nativo para Windows)

```bash
pip install waitress
waitress-serve --host=0.0.0.0 --port=5000 wsgi:application
```

### Linux — Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:application
```

### Linux — systemd service (para arranque automático)

Crear `/etc/systemd/system/claro-asistencia.service`:

```ini
[Unit]
Description=Claro Ventas Attendance Dashboard
After=network.target

[Service]
User=www-data
WorkingDirectory=/ruta/al/proyecto/claro-asistencia
Environment="PATH=/ruta/al/proyecto/claro-asistencia/venv/bin"
ExecStart=/ruta/al/proyecto/claro-asistencia/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable claro-asistencia
sudo systemctl start claro-asistencia
```

---

## API REST

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/` | Dashboard principal |
| GET | `/api/health` | Estado de la conexión MySQL |
| GET | `/api/dashboard` | Todos los datos en una sola llamada |
| GET | `/api/kpis` | Indicadores KPI |
| GET | `/api/supervisors` | Resumen por supervisor |
| GET | `/api/attendance` | Detalle de asesores |
| GET | `/api/timeline` | Datos de línea de tiempo |
| GET | `/api/filters` | Opciones disponibles para filtros |

### Parámetros de filtro (todos opcionales)

```
?supervisor=Nombre%20Supervisor
?campana=Claro%20-%20Movil%20Tmk%20Bogota
?estado=Asistio | Ausente | Retardo
?hora_inicio=07:00&hora_fin=08:30
```

---

## Funcionalidades del dashboard

- **KPIs en tiempo real**: Programados, Asistieron, Ausentes, Retardos y sus porcentajes.
- **4 gráficas interactivas**: Barras por supervisor, dona global, ranking horizontal, línea de tiempo.
- **Tabla de supervisores** con semáforo de ausentismo (verde < 5%, amarillo 5–10%, rojo > 10%).
- **Tabla de asesores** con búsqueda, ordenamiento por columna, paginación y exportación a Excel/CSV.
- **Actualización automática** cada 60 segundos con contador regresivo visible.
- **Filtros dinámicos** por supervisor, campaña, estado y franja horaria.

---

## Resolución de problemas

| Error | Causa probable | Solución |
|---|---|---|
| `Can't connect to MySQL` | Credenciales incorrectas o servidor inaccesible | Verificar `.env` y que el puerto 3306 esté abierto |
| `Access denied for user` | Permisos insuficientes | Otorgar permisos SELECT sobre `bbdd_config.*` |
| `ModuleNotFoundError` | Entorno virtual no activado | Ejecutar `venv\Scripts\activate` |
| Dashboard muestra `—` | Sin datos para la fecha actual | Normal fuera de horario laboral; verificar `CURDATE()` |
| Gráficas no cargan | CDN bloqueado por red | Descargar Chart.js y SheetJS localmente (ver sección siguiente) |

### Uso offline (sin acceso a CDN)

Si el servidor no tiene acceso a internet, descarga las librerías localmente:

```bash
# En static/js/
curl -o static/js/chart.umd.min.js https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js
curl -o static/js/xlsx.full.min.js  https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js
```

Luego actualiza las rutas en `templates/index.html`:

```html
<script src="/static/js/chart.umd.min.js"></script>
<script src="/static/js/xlsx.full.min.js"></script>
```
