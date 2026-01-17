import os
from cachelib import SimpleCache

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class BaseConfig:
    """Base configuration shared by all environments."""
    SECRET_KEY = os.environ.get('SECRET_KEY')  # Must be set in production
    SESSION_COOKIE_NAME = "chess_session"

    # 🗄️ Flask-Session (shared defaults)
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = os.path.join(BASE_DIR, 'flask_session')
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True
    }

class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False # Enables testing mode
    # Use fixed key for development - sessions must persist across requests
    # DO NOT use secrets.token_hex() here - it generates a new key on each import!
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = (
    "mysql+pymysql://chess_user:strongpassword@localhost/chess_app_dev"
)

class TestingConfig(BaseConfig):
    DEBUG = True
    TESTING = True
    SECRET_KEY = 'test-secret-key-for-testing-only'
    SQLALCHEMY_DATABASE_URI = (
        "mysql+pymysql://chess_tester:strongpassword@localhost/chess_app_test"
    )
    
    # 🗄️ Use filesystem sessions for tests that check session files
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = os.path.join(BASE_DIR, 'flask_session')
    SESSION_PERMANENT = True  # Make sessions persist in testing
    SESSION_USE_SIGNER = True

class TestingConfigFilesystem(BaseConfig):
    """Testing config that uses filesystem sessions (for session file tests)"""
    DEBUG = False
    TESTING = True
    SECRET_KEY = 'test-secret-key-for-testing-only'
    SQLALCHEMY_DATABASE_URI = (
        "mysql+pymysql://chess_tester:strongpassword@localhost/chess_app_test"
    )
    
    # 🗄️ Use filesystem sessions for tests that check session files
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = os.path.join(BASE_DIR, 'flask_session')
    SESSION_PERMANENT = True  # ← CHANGED: Must be True for E2E tests so sessions persist across reloads
    SESSION_USE_SIGNER = True

class ProductionConfig(BaseConfig):
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # MUST be set in PythonAnywhere's wsgi file or environment
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    # Sessions — filesystem works fine on PA
    SESSION_TYPE = "filesystem"
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True

    # Optional: reduce noise
    SESSION_FILE_DIR = os.environ.get(
        "SESSION_FILE_DIR",
        os.path.join(BASE_DIR, "flask_session")
    )