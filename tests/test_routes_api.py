import pytest
import json
import chess
from app import app  # make sure your Flask app is imported correctly

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['AI_ENABLED'] = False
    with app.test_client() as client:
        yield client

def reset_board(client):
    client.post("/reset")

def make_move(client, from_sq, to_sq, promotion=None):
    payload = {"from": from_sq, "to": to_sq}
    if promotion:
        payload["promotion"] = promotion
    rv = client.post("/move", data=json.dumps(payload), content_type="application/json")
    return rv.get_json()

def test_home(client, monkeypatch):
    # Monkeypatch render_template to avoid TemplateNotFound
    monkeypatch.setattr("routes.render_template", lambda x: "OK")
    rv = client.get("/")
    assert rv.status_code == 200

def test_reset(client):
    reset_board(client)
    # After reset, board should be at starting position
    rv = make_move(client, "e2", "e4")
    assert rv["status"] == "ok"

def test_legal_move(client):
    reset_board(client)
    rv = make_move(client, "e2", "e4")
    assert rv["status"] == "ok"
    # Verify e4 has white pawn
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.E4).symbol() == "P"

def test_illegal_move(client):
    reset_board(client)
    rv = make_move(client, "e2", "e5")  # invalid move
    assert rv["status"] == "illegal"

def test_promotion(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Simple promotion: clear a path with the a-pawn
    moves = [
        ("a2", "a4"), ("h7", "h6"),
        ("a4", "a5"), ("h6", "h5"),
        ("a5", "a6"), ("h5", "h4"),
        ("a6", "b7"), ("h4", "h3"),  # white captures b7 pawn
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    # Now promote pawn to queen (capturing the a8 rook)
    rv = make_move(client, "b7", "a8", promotion="q")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    piece = board.piece_at(chess.A8)
    assert piece.symbol().upper() == "Q"

def test_capture(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Move white pawn to capture
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    rv = make_move(client, "e4", "d5")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    piece = board.piece_at(chess.D5)
    assert piece.symbol() == "P"

def test_en_passant(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Set up en passant via API
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    make_move(client, "e4", "e5")
    make_move(client, "f7", "f5")
    rv = make_move(client, "e5", "f6")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.F5) is None
    assert board.piece_at(chess.F6).symbol() == "P"

def test_game_over_fields(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    rv = client.post('/reset')
    data = rv.get_json()
    assert data['status'] == 'ok'
    # After reset, not game over
    assert 'game_over' in data
    assert data['game_over'] == False
    assert data['fifty_moves'] == False
    assert data['repetition'] == False
    assert data['insufficient_material'] == False
