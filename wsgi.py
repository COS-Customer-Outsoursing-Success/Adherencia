# Punto de entrada para servidores de producción (gunicorn, waitress, etc.)
from app import create_app

application = create_app()

if __name__ == '__main__':
    application.run()
