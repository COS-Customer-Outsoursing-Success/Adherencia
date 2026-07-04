from routes.api import api_bp
from routes.excesos import excesos_bp
from routes.detalle_agente import detalle_agente_bp


def register_routes(app):
    app.register_blueprint(api_bp)
    app.register_blueprint(excesos_bp)
    app.register_blueprint(detalle_agente_bp)
