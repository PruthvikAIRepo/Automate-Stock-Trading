from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "dev-secret-key"

    from app.routes.main import main_bp
    app.register_blueprint(main_bp)

    from app.dummy_data import ALL_INDICES

    @app.context_processor
    def inject_indices():
        return {"indices": ALL_INDICES}

    return app
