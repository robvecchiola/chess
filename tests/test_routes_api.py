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

# -------------------------------------------------------------------
# Castling Tests
# -------------------------------------------------------------------

def test_kingside_castling_white(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Clear path for kingside castling
    make_move(client, "e2", "e4")
    make_move(client, "e7", "e5")
    make_move(client, "g1", "f3")
    make_move(client, "g8", "f6")
    make_move(client, "f1", "e2")
    make_move(client, "f8", "e7")
    # Castle kingside
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.G1).symbol() == "K"
    assert board.piece_at(chess.F1).symbol() == "R"

def test_queenside_castling_white(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Clear path for queenside castling
    make_move(client, "d2", "d4")
    make_move(client, "d7", "d5")
    make_move(client, "b1", "c3")
    make_move(client, "b8", "c6")
    make_move(client, "c1", "f4")
    make_move(client, "c8", "f5")
    make_move(client, "d1", "d2")
    make_move(client, "d8", "d7")
    # Castle queenside
    rv = make_move(client, "e1", "c1")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.C1).symbol() == "K"
    assert board.piece_at(chess.D1).symbol() == "R"

def test_castling_after_king_moved(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Move king and try to castle
    make_move(client, "e2", "e4")
    make_move(client, "e7", "e5")
    make_move(client, "e1", "e2")
    make_move(client, "e8", "e7")
    make_move(client, "e2", "e1")
    make_move(client, "e7", "e8")
    make_move(client, "g1", "f3")
    make_move(client, "g8", "f6")
    make_move(client, "f1", "e2")
    make_move(client, "f8", "e7")
    # Try to castle - should be illegal
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "illegal"

# -------------------------------------------------------------------
# Move History & Captured Pieces Tests
# -------------------------------------------------------------------

def test_move_history_san_notation(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    make_move(client, "e2", "e4")
    rv = make_move(client, "e7", "e5")
    assert "move_history" in rv
    assert len(rv["move_history"]) == 2
    assert rv["move_history"][0] == "e4"
    assert rv["move_history"][1] == "e5"

def test_captured_pieces_tracking(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Set up capture - white captures black pawn
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    rv = make_move(client, "e4", "d5")
    assert "captured_pieces" in rv
    assert len(rv["captured_pieces"]["white"]) == 1  # White captured a black pawn
    assert rv["captured_pieces"]["white"][0].lower() == "p"

def test_captured_pieces_both_colors(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # White captures black pawn
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    make_move(client, "e4", "d5")  # White captures black pawn
    # Black captures white pawn
    rv = make_move(client, "d8", "d5")  # Black queen captures white pawn on d5
    assert len(rv["captured_pieces"]["white"]) == 1  # White captured 1 black pawn
    assert len(rv["captured_pieces"]["black"]) == 1  # Black captured 1 white pawn

def test_en_passant_capture_tracking(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Set up en passant - white captures black pawn
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    make_move(client, "e4", "e5")
    make_move(client, "f7", "f5")
    rv = make_move(client, "e5", "f6")  # White captures via en passant
    # En passant should track captured pawn in white's captures
    assert len(rv["captured_pieces"]["white"]) == 1
    assert rv["captured_pieces"]["white"][0].lower() == "p"

# -------------------------------------------------------------------
# Promotion Variant Tests
# -------------------------------------------------------------------

def test_promotion_to_rook(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    moves = [
        ("a2", "a4"), ("h7", "h6"),
        ("a4", "a5"), ("h6", "h5"),
        ("a5", "a6"), ("h5", "h4"),
        ("a6", "b7"), ("h4", "h3"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    rv = make_move(client, "b7", "a8", promotion="r")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.A8).symbol().upper() == "R"

def test_promotion_to_bishop(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    moves = [
        ("a2", "a4"), ("h7", "h6"),
        ("a4", "a5"), ("h6", "h5"),
        ("a5", "a6"), ("h5", "h4"),
        ("a6", "b7"), ("h4", "h3"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    rv = make_move(client, "b7", "a8", promotion="b")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.A8).symbol().upper() == "B"

def test_promotion_to_knight(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    moves = [
        ("a2", "a4"), ("h7", "h6"),
        ("a4", "a5"), ("h6", "h5"),
        ("a5", "a6"), ("h5", "h4"),
        ("a6", "b7"), ("h4", "h3"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    rv = make_move(client, "b7", "a8", promotion="n")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.A8).symbol().upper() == "N"

# -------------------------------------------------------------------
# Error Handling Tests
# -------------------------------------------------------------------

def test_malformed_json(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    rv = client.post("/move", data="{invalid json}", content_type="application/json")
    assert rv.status_code in [400, 500]  # Should handle gracefully

def test_missing_from_field(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    payload = {"to": "e4"}
    rv = client.post("/move", data=json.dumps(payload), content_type="application/json")
    data = rv.get_json()
    assert data["status"] == "illegal"

def test_missing_to_field(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    payload = {"from": "e2"}
    rv = client.post("/move", data=json.dumps(payload), content_type="application/json")
    data = rv.get_json()
    assert data["status"] == "illegal"

def test_invalid_uci_string(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    rv = make_move(client, "z9", "z1")
    assert rv["status"] == "illegal"

# -------------------------------------------------------------------
# Session Persistence Tests
# -------------------------------------------------------------------

def test_session_persists_across_requests(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Make first move
    make_move(client, "e2", "e4")
    # Make second move - should remember first
    rv = make_move(client, "e7", "e5")
    assert len(rv["move_history"]) == 2
    assert rv["move_history"][0] == "e4"

def test_reset_clears_session(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Make moves
    make_move(client, "e2", "e4")
    make_move(client, "e7", "e5")
    # Reset
    rv = client.post("/reset")
    data = rv.get_json()
    assert data["move_history"] == []
    assert data["captured_pieces"] == {'white': [], 'black': []}
    assert data["fen"] == chess.STARTING_FEN

# -------------------------------------------------------------------
# Edge Case Tests
# -------------------------------------------------------------------

def test_multiple_captures_sequence(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Set up multiple captures
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    make_move(client, "e4", "d5")  # White captures black pawn
    make_move(client, "d8", "d5")  # Black captures white pawn
    make_move(client, "b1", "c3")
    make_move(client, "d5", "e5")  # Move queen away
    make_move(client, "c3", "e4")
    rv = make_move(client, "e5", "e4")  # Black queen captures white knight
    assert len(rv["captured_pieces"]["white"]) == 1  # White captured 1 black pawn
    assert len(rv["captured_pieces"]["black"]) == 2  # Black captured 1 pawn + 1 knight

def test_reset_during_checkmate(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Fool's mate
    moves = [("f2","f3"), ("e7","e5"), ("g2","g4"), ("d8","h4")]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    # Reset should work even after checkmate
    rv = client.post("/reset")
    data = rv.get_json()
    assert data["status"] == "ok"
    assert data["checkmate"] == False
    assert data["game_over"] == False
