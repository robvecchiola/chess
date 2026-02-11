import json

from app import create_app
from config import DevelopmentConfig, TestingConfig


def test_test_set_position_requires_testing():
    app = create_app(DevelopmentConfig)
    with app.test_client() as client:
        payload = {"fen": "8/8/8/8/8/8/8/8 w - - 0 1"}
        rv = client.post(
            "/test/set_position",
            data=json.dumps(payload),
            content_type="application/json",
        )

    assert rv.status_code == 403
    data = rv.get_json()
    assert "testing mode" in data["error"].lower()


def test_test_set_position_accepts_valid_fen():
    app = create_app(TestingConfig)
    app.config["TESTING"] = True

    with app.test_client() as client:
        payload = {"fen": "8/8/8/8/8/8/8/8 w - - 0 1"}
        rv = client.post(
            "/test/set_position",
            data=json.dumps(payload),
            content_type="application/json",
        )

    data = rv.get_json()
    assert data["status"] == "ok"
    assert data["fen"].split()[0] == payload["fen"].split()[0]
    assert data["move_history"] == []
