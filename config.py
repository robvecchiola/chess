import os

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
    
    # ⚡ Use cachelib for tests (in-memory but persists within process)
    # This is synchronous and reliable for E2E tests
    SESSION_TYPE = 'cachelib'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_FILE_DIR = None

class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
    # Add production-specific configs here, e.g., database URIs