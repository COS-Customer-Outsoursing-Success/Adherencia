"""Bloquea el acceso al dashboard desde navegadores móviles (Android/iOS).

No es una medida de seguridad infalible (el User-Agent se puede falsear),
pero bloquea el uso normal desde celulares/tablets.
"""
import re

from flask import request

_MOBILE_UA_PATTERN = re.compile(r"Android|iPhone|iPad|iPod|Mobile", re.IGNORECASE)

BLOCKED_PAGE_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Acceso no disponible</title>
<style>
  body { font-family: -apple-system, Inter, sans-serif; background:#F5F5F5; display:flex;
         align-items:center; justify-content:center; height:100vh; margin:0; padding:20px;
         text-align:center; }
  .box { background:#fff; border-radius:14px; padding:32px 24px; max-width:380px;
         box-shadow:0 4px 16px rgba(0,0,0,0.1); border-top:4px solid #DA291C; }
  .logo { font-weight:700; color:#DA291C; font-size:1.3rem; margin-bottom:12px; }
  h1 { font-size:1.1rem; color:#212121; margin:0 0 10px; }
  p { font-size:0.9rem; color:#616161; line-height:1.5; margin:0; }
</style>
</head>
<body>
  <div class="box">
    <div class="logo">claro</div>
    <h1>Contenido no disponible en este dispositivo</h1>
    <p>Este panel solo está disponible desde un computador. Por favor ingresa desde un equipo de escritorio o portátil.</p>
  </div>
</body>
</html>
"""


def is_mobile_request() -> bool:
    user_agent = request.headers.get("User-Agent", "")
    return bool(_MOBILE_UA_PATTERN.search(user_agent))
