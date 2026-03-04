import json
import os

from flask import Flask

from config.settings import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure runtime directories exist
    os.makedirs(app.config["TEMP_DIR"], exist_ok=True)
    os.makedirs(app.config["OUTPUT_DIR"], exist_ok=True)

    # Load speakers config
    with open(app.config["SPEAKERS_CONFIG"], "r") as f:
        app.config["SPEAKERS"] = json.load(f)

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
