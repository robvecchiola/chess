"""
Pytest configuration and fixtures for E2E tests
This file is automatically discovered by pytest and provides shared fixtures
"""
import pytest
import threading
import time
from app import app as flask_app


@pytest.fixture(scope="session")
def flask_server():
    """
    Start Flask server in background thread for E2E tests
    Returns the base URL (e.g., http://localhost:5000)
    """
    # Configure Flask for testing
    flask_app.config['TESTING'] = True
    flask_app.config['AI_ENABLED'] = True  # Enable AI for E2E tests
    flask_app.config['DEBUG'] = False  # Disable debug mode in tests
    
    # Use a specific port for testing
    port = 5000
    base_url = f"http://localhost:{port}"
    
    # Start Flask in a background thread
    def run_server():
        flask_app.run(port=port, use_reloader=False, threaded=True)
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to be ready
    max_retries = 10
    for i in range(max_retries):
        try:
            import urllib.request
            urllib.request.urlopen(base_url, timeout=1)
            break
        except Exception:
            if i == max_retries - 1:
                raise RuntimeError("Flask server failed to start")
            time.sleep(0.5)
    
    yield base_url
    
    # Server thread will be killed when test session ends (daemon=True)


# Note: client fixtures are defined in individual test files
# (test_routes_api.py and test_ai_and_endgames.py)
# This avoids fixture conflicts and allows per-file AI_ENABLED configuration