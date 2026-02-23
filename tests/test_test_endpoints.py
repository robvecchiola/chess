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

def test_test_set_position_requires_fen_field():
    app = create_app(TestingConfig)
    app.config["TESTING"] = True

    with app.test_client() as client:
        rv = client.post(
            "/test/set_position",
            data=json.dumps({}),
            content_type="application/json",
        )

    assert rv.status_code == 400
    data = rv.get_json()
    assert "fen required" in data["error"].lower()

def test_test_set_position_rejects_invalid_fen():
    app = create_app(TestingConfig)
    app.config["TESTING"] = True

    with app.test_client() as client:
        rv = client.post(
            "/test/set_position",
            data=json.dumps({"fen": "not a fen"}),
            content_type="application/json",
        )

    assert rv.status_code == 400
    data = rv.get_json()
    assert "invalid fen" in data["error"].lower()

def test_test_set_position_reuses_existing_active_game():
    app = create_app(TestingConfig)
    app.config["TESTING"] = True

    with app.test_client() as client:
        payload = {"fen": "8/8/8/8/8/8/8/8 w - - 0 1"}
        first = client.post(
            "/test/set_position",
            data=json.dumps(payload),
            content_type="application/json",
        ).get_json()
        with client.session_transaction() as sess:
            first_game_id = sess.get("game_id")

        second = client.post(
            "/test/set_position",
            data=json.dumps(payload),
            content_type="application/json",
        ).get_json()
        with client.session_transaction() as sess:
            second_game_id = sess.get("game_id")

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert first_game_id is not None
    assert second_game_id == first_game_id


def test_test_set_position_parses_special_move_color_prefixes():
    app = create_app(TestingConfig)
    app.config["TESTING"] = True

    with app.test_client() as client:
        payload = {
            "fen": "8/8/8/8/8/8/8/8 w - - 0 1",
            "special_moves": ["White: Castling", "Black: Promotion to Q", "En Passant"],
        }
        rv = client.post(
            "/test/set_position",
            data=json.dumps(payload),
            content_type="application/json",
        )

    data = rv.get_json()
    assert data["status"] == "ok"
    assert data["special_moves_by_color"]["white"] == ["Castling", "En Passant"]
    assert data["special_moves_by_color"]["black"] == ["Promotion to Q"]


def test_test_set_position_defaults_unprefixed_special_moves_to_white():
    app = create_app(TestingConfig)
    app.config["TESTING"] = True

    with app.test_client() as client:
        payload = {
            "fen": "8/8/8/8/8/8/8/8 w - - 0 1",
            "special_moves": ["Castling", "Promotion to R"],
        }
        rv = client.post(
            "/test/set_position",
            data=json.dumps(payload),
            content_type="application/json",
        )

    data = rv.get_json()
    assert data["status"] == "ok"
    assert data["special_moves_by_color"]["white"] == ["Castling", "Promotion to R"]
    assert data["special_moves_by_color"]["black"] == []
