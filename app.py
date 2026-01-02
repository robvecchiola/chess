from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from routes import register_routes

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_object):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)

    app.secret_key = app.config["SECRET_KEY"]
    Session(app)

    register_routes(app)

    return app

if __name__ == "__main__":
    from config import DevelopmentConfig
    app = create_app(DevelopmentConfig)
    app.run(debug=app.config["DEBUG"])
