import logging
import sys

from flask import Flask, request

from config import Config
from routes import register_routes
from utils.device_guard import BLOCKED_PAGE_HTML, is_mobile_request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = Config.SECRET_KEY

    register_routes(app)

    @app.before_request
    def block_mobile_devices():
        if request.path.startswith("/static/"):
            return None
        if is_mobile_request():
            return BLOCKED_PAGE_HTML, 403

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
    )
