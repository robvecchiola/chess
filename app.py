import os
import logging
from flask import Flask
from flask_session import Session
from extensions import db
from flask_migrate import Migrate
from routes import register_routes
from logging_config import setup_logging

logger = logging.getLogger(__name__)

def create_app(config_object=None):
    app = Flask(__name__)

    # -------------------------------------------------
    # Select configuration
    # -------------------------------------------------
    if config_object:
        # Explicit config (used by pytest, wsgi, manual runs)
        app.config.from_object(config_object)
        config_source = "explicit"
    else:
        # Automatic selection via FLASK_ENV
        env = os.environ.get("FLASK_ENV", "development")

        if env == "production":
            app.config.from_object("config.ProductionConfig")
            config_source = "production"
        elif env == "testing":
            app.config.from_object("config.TestingConfig")
            config_source = "testing"
        else:
            app.config.from_object("config.DevelopmentConfig")
            config_source = "development"

    # -------------------------------------------------
    # Setup logging
    # -------------------------------------------------
    setup_logging(
        level="DEBUG" if app.config.get("DEBUG") else "INFO"
    )
    logger.info(
        "Flask app initialized | config=%s | debug=%s | ai_enabled=%s",
        config_source,
        app.config.get("DEBUG"),
        app.config.get("AI_ENABLED", True)
    )

    # -------------------------------------------------
    # Extensions
    # -------------------------------------------------
    db.init_app(app)
    Migrate(app, db)

    app.secret_key = app.config["SECRET_KEY"]
    Session(app)

    # -------------------------------------------------
    # Routes
    # -------------------------------------------------
    register_routes(app)

    return app


# -------------------------------------------------
# Local development only
# -------------------------------------------------
if __name__ == "__main__":
    from config import DevelopmentConfig
    app = create_app(DevelopmentConfig)
    app.run(debug=app.config["DEBUG"])
