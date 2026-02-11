import pytest
from datetime import datetime

from app import create_app
from config import TestingConfig
from models import Game, db


app = create_app(TestingConfig)


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client


def _create_game(result, *, ai_enabled=True, ended=True):
    game = Game(
        ai_enabled=ai_enabled,
        state="finished" if ended else "active",
        result=result if ended else None,
        termination_reason="test" if ended else None,
        ended_at=datetime.utcnow() if ended else None,
    )
    db.session.add(game)
    return game


def test_ai_record_empty(client):
    with app.app_context():
        Game.query.delete()
        db.session.commit()

    rv = client.get("/stats/ai-record")
    data = rv.get_json()

    assert data["wins"] == 0
    assert data["losses"] == 0
    assert data["draws"] == 0
    assert data["total"] == 0
    assert data["win_rate"] == 0.0


def test_ai_record_counts_results(client):
    with app.app_context():
        Game.query.delete()
        db.session.commit()

        _create_game("0-1")  # AI (black) win
        _create_game("0-1")  # AI win
        _create_game("1-0")  # AI loss
        _create_game("1/2-1/2")  # draw
        _create_game("0-1", ai_enabled=False)  # should not count
        _create_game("0-1", ended=False)  # should not count
        db.session.commit()

    rv = client.get("/stats/ai-record")
    data = rv.get_json()

    assert data["wins"] == 2
    assert data["losses"] == 1
    assert data["draws"] == 1
    assert data["total"] == 4
    assert data["win_rate"] == 50.0
