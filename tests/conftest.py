"""
Pytest configuration and shared fixtures.
"""

import threading
import time
from pathlib import Path

import pytest
from flask_migrate import upgrade

from app import create_app
from config import TestingConfig


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    app = create_app(TestingConfig)

    with app.app_context():
        uri = app.config["SQLALCHEMY_DATABASE_URI"]
        assert "test" in uri, f"Refusing to migrate non-test DB: {uri}"
        upgrade()

    yield


@pytest.fixture(scope="session")
def e2e_session_dir(tmp_path_factory):
    """Use a unique Flask-Session directory per pytest session."""
    return Path(tmp_path_factory.mktemp("flask_session"))


@pytest.fixture(scope="session")
def flask_server(e2e_session_dir):
    from config import TestingConfigFilesystem

    class E2ETestingConfig(TestingConfigFilesystem):
        SESSION_FILE_DIR = str(e2e_session_dir)

    flask_app = create_app(E2ETestingConfig)
    flask_app.config["TESTING"] = True
    flask_app.config["AI_ENABLED"] = True
    flask_app.config["DEBUG"] = False

    port = 5000
    base_url = f"http://localhost:{port}"

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


@pytest.fixture(autouse=True)
def cleanup_flask_session(e2e_session_dir):
    """
    Clean Flask-Session files and game DB records before each test.
    """
    session_dir = Path(e2e_session_dir)

    if session_dir.exists():
        for session_file in session_dir.glob("*"):
            if session_file.is_file():
                try:
                    session_file.unlink()
                    print(f"[CLEANUP] Removed session file: {session_file.name}")
                except Exception as e:
                    print(f"[CLEANUP] Failed to remove {session_file.name}: {e}")

    try:
        from config import TestingConfigFilesystem
        from extensions import db
        from models import Game, GameMove

        class CleanupConfig(TestingConfigFilesystem):
            SESSION_FILE_DIR = str(e2e_session_dir)

        app = create_app(CleanupConfig)
        with app.app_context():
            GameMove.query.delete()
            Game.query.delete()
            db.session.commit()
            print("[CLEANUP] Cleared database Game records")

            db.engine.dispose()
            print("[CLEANUP] Disposed database engine connections")
    except Exception as e:
        print(f"[CLEANUP] Warning: Failed to clear database: {e}")

    yield


@pytest.fixture(autouse=True)
def seed_rng():
    """Set deterministic RNG before each test."""
    import random

    seed = 42
    random.seed(seed)

    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass

    yield


@pytest.fixture(autouse=True)
def clear_page_cookies(request):
    """Clear browser cookies before each Playwright test for session isolation."""
    if "page" in request.fixturenames:
        page = request.getfixturevalue("page")
        page.context.clear_cookies()
        print(f"[FIXTURE] Cleared cookies before test: {request.node.name}")

    yield
