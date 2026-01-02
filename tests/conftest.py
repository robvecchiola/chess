"""
Pytest configuration and fixtures for E2E tests
This file is automatically discovered by pytest and provides shared fixtures
"""
import pytest
import threading
import time
from config import TestingConfig
from flask_migrate import upgrade
from app import create_app

@pytest.fixture(scope="session", autouse=True)

def setup_test_db():
    app = create_app(TestingConfig)

    with app.app_context():
        uri = app.config["SQLALCHEMY_DATABASE_URI"]
        assert "test" in uri, f"Refusing to migrate non-test DB: {uri}"
        upgrade()

    yield

@pytest.fixture(scope="session")
def flask_server():
    flask_app = create_app(TestingConfig)
    flask_app.config['AI_ENABLED'] = True
    flask_app.config['DEBUG'] = False

    port = 5000
    base_url = f"http://localhost:{port}"
    
    # Start Flask in a background thread
    def run_server():
        flask_app.run(port=port, use_reloader=False, threaded=True)

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    for _ in range(10):
        try:
            import urllib.request
            urllib.request.urlopen(base_url, timeout=1)
            break
        except Exception:
            time.sleep(0.5)

    yield base_url
    
    # Server thread will be killed when test session ends (daemon=True)


# Note: client fixtures are defined in individual test files
# (test_routes_api.py and test_ai_and_endgames.py)
# This avoids fixture conflicts and allows per-file AI_ENABLED configuration