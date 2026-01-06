import os
from flask import Flask
from flask_session import Session
from extensions import db
from flask_migrate import Migrate
from routes import register_routes

def create_app(config_object=None):
    app = Flask(__name__)

    # -------------------------------------------------
    # Select configuration
    # -------------------------------------------------
    if config_object:
        # Explicit config (used by pytest, wsgi, manual runs)
        app.config.from_object(config_object)
    else:
        # Automatic selection via FLASK_ENV
        env = os.environ.get("FLASK_ENV", "development")

        if env == "production":
            app.config.from_object("config.ProductionConfig")
        elif env == "testing":
            app.config.from_object("config.TestingConfig")
        else:
            app.config.from_object("config.DevelopmentConfig")

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
