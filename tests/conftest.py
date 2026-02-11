"""
Pytest configuration and fixtures for E2E tests
This file is automatically discovered by pytest and provides shared fixtures
"""
import pytest
import threading
import time
import os
import shutil
from pathlib import Path
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
    from config import TestingConfigFilesystem
    flask_app = create_app(TestingConfigFilesystem)
    flask_app.config['TESTING'] = True        # ← Enable testing mode for /test endpoints
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


# 🔑 CRITICAL: Test Isolation Fixture - Prevents Flask-Session Pollution
# Each test gets a fresh session by clearing the filesystem session cache
@pytest.fixture(autouse=True)
def cleanup_flask_session():
    """
    Ensure Flask-Session files don't pollute between tests.
    
    Problem: Flask-Session stores data in files in flask_session/ directory.
    When tests run in sequence, old session files can interfere with new tests,
    causing flaky failures where tests pass individually but fail in suite.
    
    Solution: Clean up session directory before each test.
    Also cleans up database Game records to prevent spillover.
    """
    # Cleanup BEFORE the test runs
    # (Using a fixture without explicit setup/teardown means it runs before and after)
    
    session_dir = Path("flask_session")
    
    # Remove all session files to ensure fresh state
    if session_dir.exists():
        for session_file in session_dir.glob("*"):
            if session_file.is_file():
                try:
                    session_file.unlink()
                    print(f"[CLEANUP] Removed session file: {session_file.name}")
                except Exception as e:
                    print(f"[CLEANUP] Failed to remove {session_file.name}: {e}")
    
    # Also clear database Game records to ensure clean state
    # This prevents AI records from previous tests affecting later tests
    try:
        from app import create_app
        from config import TestingConfigFilesystem
        from extensions import db
        from models import Game, GameMove
        
        app = create_app(TestingConfigFilesystem)
        
        with app.app_context():
            # Delete all game records to start fresh
            GameMove.query.delete()
            Game.query.delete()
            db.session.commit()
            print(f"[CLEANUP] Cleared database Game records")
            
            # 🔑 CRITICAL: Properly dispose the engine to return all connections to pool
            # This is required to prevent "Too many connections" errors in large test suites
            db.engine.dispose()
            print(f"[CLEANUP] Disposed database engine connections")
    except Exception as e:
        print(f"[CLEANUP] Warning: Failed to clear database: {e}")
    
    # Yield control to test - test runs here
    yield
    
    # Cleanup AFTER the test runs (optional - prevents DB bloat)
    # The before-cleanup is what prevents pollution, but we can also cleanup after
    # to prevent accumulation of test data


# 🔑 CRITICAL: RNG Seed Fixture - Stabilizes AI Randomness for Tests
@pytest.fixture(autouse=True)
def seed_rng():
    """
    Set a fixed random seed before each test to stabilize RNG-dependent behavior.
    
    This allows:
    - Quiescence and minimax searches to be deterministic within a test run.
    - AI move selection to be repeatable across test runs (same seed = same moves).
    - Tests to assert on move equality or properties reliably.
    
    Why autouse=True: Makes every test deterministic by default. Tests that need
    nondeterminism can override this fixture in their module.
    """
    import random
    
    SEED = 42
    random.seed(SEED)
    
    # Try to seed numpy if available
    try:
        import numpy as np
        np.random.seed(SEED)
    except ImportError:
        pass  # numpy not installed, no-op
    
    yield
    
    # No cleanup needed; next test will set seed again


# 🔑 CRITICAL: Clear Browser Cookies Before Each E2E Test
# Even though cleanup_flask_session deletes session files, the browser context
# may retain old session cookies from previous tests. When a new test calls
# page.goto(live_server), it uses the old cookie and loads the old session!
# This fixture ensures every test starts with a clean browser state.
@pytest.fixture(autouse=True)
def clear_page_cookies(request):
    """
    Automatically clear browser cookies before each E2E Playwright test.
    
    Without this, tests in the E2E suite fail because:
    1. Test A completes, browser context retains session cookie
    2. Test B starts, calls page.goto(live_server)
    3. Page.goto uses old cookie, loads Test A's session
    4. setup_board_position tries to set Test B's position but fails
       because the page already loaded Test A's data
    5. Test B fails with wrong FEN/material
    
    Solution: Clear all cookies before each test runs, so every test
    gets a truly fresh browser state.
    """
    # Only clear for E2E tests that use the 'page' fixture
    if 'page' in request.fixturenames:
        # The page fixture is provided by pytest-playwright
        # We access it by getting the fixture value
        page = request.getfixturevalue('page')
        page.context.clear_cookies()
        print(f"[FIXTURE] Cleared cookies before test: {request.node.name}")
    
    yield
# (test_routes_api.py and test_ai_and_endgames.py)
# This avoids fixture conflicts and allows per-file AI_ENABLED configuration