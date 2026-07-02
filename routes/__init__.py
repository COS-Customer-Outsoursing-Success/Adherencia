from routes.api import api_bp


def register_routes(app):
    app.register_blueprint(api_bp)
