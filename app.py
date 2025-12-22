from flask import Flask
from flask_session import Session
from config import DevelopmentConfig
from routes import register_routes

app = Flask(__name__)

# Load configuration
app.config.from_object(DevelopmentConfig)

# 🔑 Required for sessions
app.secret_key = app.config['SECRET_KEY']

# Initialize Flask-Session
Session(app)

# Register routes AFTER session setup
register_routes(app)

if __name__ == "__main__":
    app.run(debug=app.config['DEBUG'])