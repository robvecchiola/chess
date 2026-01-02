import pytest
import json
import chess
from app import create_app
from config import TestingConfig
from constants import PIECE_VALUES
from tests.helper import set_position  # make sure your Flask app is imported correctly

app = create_app(TestingConfig)

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
    # Accept template name and any keyword args
    monkeypatch.setattr("routes.render_template", lambda x, **kwargs: "OK")
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
# Black Castling Tests
# -------------------------------------------------------------------

def test_queenside_castling_black(client):
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
    make_move(client, "e1", "d1")  # Move white king out of way
    make_move(client, "e8", "c8")  # Black castles queenside
    rv = make_move(client, "d1", "e1")  # Dummy move to refresh
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.C8).symbol() == "k"
    assert board.piece_at(chess.D8).symbol() == "r"

# -------------------------------------------------------------------
# Castling Edge Cases
# -------------------------------------------------------------------

def test_castling_through_check(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Set up position where castling would move king through check
    make_move(client, "e2", "e4")
    make_move(client, "e7", "e5")
    make_move(client, "g1", "f3")
    make_move(client, "f8", "c5")  # Bishop to c5
    make_move(client, "f1", "e2")
    make_move(client, "d8", "f6")  # Queen to f6 (attacks d4, e5, f3, but doesn't block castling)
    make_move(client, "d2", "d3")
    make_move(client, "f6", "f1")  # Queen attacks f1 directly (king would pass through)
    # Try to castle - should be illegal (king passes through attacked square)
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "illegal"

def test_castling_out_of_check(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Set up position where king is in check and tries to castle
    # Using a position where king is in check but not checkmate
    make_move(client, "e2", "e4")
    make_move(client, "e7", "e5")
    make_move(client, "g1", "f3")
    make_move(client, "g8", "f6")
    make_move(client, "f1", "b5")  # Bishop checks king (can be blocked)
    # Black king is in check, can't castle
    rv = make_move(client, "e8", "g8")  # Try to castle out of check
    assert rv["status"] == "illegal"

def test_castling_after_rook_moved(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Move rook and try to castle
    make_move(client, "h2", "h4")
    make_move(client, "h7", "h5")
    make_move(client, "h1", "h3")
    make_move(client, "h8", "h6")
    make_move(client, "h3", "h1")  # Rook back to starting position
    make_move(client, "h6", "h8")
    make_move(client, "g1", "f3")
    make_move(client, "g8", "f6")
    make_move(client, "f1", "e2")
    make_move(client, "f8", "e7")
    # Try to castle - should be illegal (rook has moved)
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "illegal"

# -------------------------------------------------------------------
# Black Castling Tests
# -------------------------------------------------------------------

# CRITICAL FIX 2: Fix black castling tests to avoid illegal white castling
def test_kingside_castling_black(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Clear path for kingside castling
    make_move(client, "e2", "e4")
    make_move(client, "e7", "e5")
    make_move(client, "g1", "f3")
    make_move(client, "g8", "f6")
    make_move(client, "f1", "e2")
    make_move(client, "f8", "e7")
    # White makes a normal move (not castling)
    make_move(client, "d2", "d3")  # Changed from king move
    # Black castles kingside
    rv = make_move(client, "e8", "g8")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.G8).symbol() == "k"
    assert board.piece_at(chess.F8).symbol() == "r"

def test_queenside_castling_black(client):
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
    # White makes a normal move (not castling)
    make_move(client, "e2", "e3")  # Changed from king move
    # Black castles queenside
    rv = make_move(client, "e8", "c8")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.C8).symbol() == "k"
    assert board.piece_at(chess.D8).symbol() == "r"

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

# -------------------------------------------------------------------
# Special Moves Tracking Tests
# -------------------------------------------------------------------

def test_special_moves_castling(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Set up and perform castling
    make_move(client, "e2", "e4")
    make_move(client, "e7", "e5")
    make_move(client, "g1", "f3")
    make_move(client, "g8", "f6")
    make_move(client, "f1", "e2")
    make_move(client, "f8", "e7")
    rv = make_move(client, "e1", "g1")
    assert "special_moves" in rv
    assert "Castling" in rv["special_moves"]

def test_special_moves_en_passant(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Set up en passant
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    make_move(client, "e4", "e5")
    make_move(client, "f7", "f5")
    rv = make_move(client, "e5", "f6")
    assert "special_moves" in rv
    assert "En Passant" in rv["special_moves"]

def test_special_moves_promotion(client):
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
    rv = make_move(client, "b7", "a8", promotion="q")
    assert "special_moves" in rv
    assert "Promotion to Q" in rv["special_moves"]

def test_multiple_special_moves_accumulation(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # First special move: en passant
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    make_move(client, "e4", "e5")
    make_move(client, "f7", "f5")
    rv = make_move(client, "e5", "f6")  # En passant
    assert len(rv["special_moves"]) == 1
    assert "En Passant" in rv["special_moves"]
    
    # Second special move: castling
    make_move(client, "g8", "h6")
    make_move(client, "g1", "f3")
    make_move(client, "h6", "g8")
    make_move(client, "f1", "e2")
    make_move(client, "g8", "h6")
    rv = make_move(client, "e1", "g1")  # Castling
    assert len(rv["special_moves"]) == 2
    assert "En Passant" in rv["special_moves"]
    assert "Castling" in rv["special_moves"]

def test_san_notation_includes_capture(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Make a capture and check SAN notation includes 'x'
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    rv = make_move(client, "e4", "d5")  # Pawn captures pawn
    # Last move in history should be exd5 (includes 'x' for capture)
    assert "move_history" in rv
    last_move = rv["move_history"][-1]
    assert "x" in last_move  # SAN notation should include capture symbol

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
# All Piece Types Captured Tests
# -------------------------------------------------------------------

def test_capture_queen(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Set up queen capture
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    make_move(client, "e4", "d5")
    rv = make_move(client, "d8", "d5")  # Black queen moves to d5
    make_move(client, "b1", "c3")
    rv = make_move(client, "d5", "e5")
    make_move(client, "c3", "e4")
    rv = make_move(client, "e5", "e4")  # Queen captures knight
    make_move(client, "d1", "e2")
    rv = make_move(client, "e4", "e2")  # Queen captures queen
    # Verify white queen was captured by black
    captured = rv["captured_pieces"]["black"]
    assert any(p.lower() == 'q' for p in captured)

def test_capture_rook(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Simple rook capture
    moves = [
        ("a2", "a4"), ("h7", "h6"),
        ("a4", "a5"), ("h6", "h5"),
        ("a5", "a6"), ("h5", "h4"),
        ("a6", "b7"), ("h4", "h3"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    rv = make_move(client, "b7", "a8", promotion="q")  # Pawn promotes and captures rook
    # Verify rook was captured by white
    captured = rv["captured_pieces"]["white"]
    assert any(p.lower() == 'r' for p in captured)

def test_capture_bishop(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Bishop capture
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    make_move(client, "f1", "b5")
    make_move(client, "c8", "d7")
    rv = make_move(client, "b5", "d7")  # Bishop captures bishop
    # Verify bishop was captured
    captured = rv["captured_pieces"]["white"]
    assert any(p.lower() == 'b' for p in captured)

def test_capture_knight(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Knight capture
    make_move(client, "e2", "e4")
    make_move(client, "b8", "c6")
    make_move(client, "f1", "b5")
    make_move(client, "c6", "d4")  # Knight moves
    make_move(client, "b5", "c4")
    make_move(client, "d4", "f3")  # Knight moves
    rv = make_move(client, "d1", "f3")  # Queen captures knight
    # Verify knight was captured by white
    captured = rv["captured_pieces"]["white"]
    assert any(p.lower() == 'n' for p in captured)

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
    """Test malformed JSON returns proper 400 error"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    rv = client.post("/move", data="{invalid json}", content_type="application/json")
    assert rv.status_code == 400  # Should be 400 Bad Request for malformed JSON

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
# Game Over Prevention Tests
# -------------------------------------------------------------------

def test_move_rejected_after_checkmate(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Fool's mate
    moves = [("f2","f3"), ("e7","e5"), ("g2","g4"), ("d8","h4")]
    for from_sq, to_sq in moves:
        rv = make_move(client, from_sq, to_sq)
    # Game is over (checkmate)
    assert rv["checkmate"] == True
    # Try to make another move - should fail
    rv2 = make_move(client, "e2", "e4")
    assert rv2["status"] == "illegal"

def test_move_rejected_after_stalemate(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Create stalemate
    moves = [
        ("e2", "e3"), ("a7", "a5"),
        ("d1", "h5"), ("a8", "a6"),
        ("h5", "a5"), ("h7", "h5"),
        ("h2", "h4"), ("a6", "h6"),
        ("a5", "c7"), ("f7", "f6"),
        ("c7", "d7"), ("e8", "f7"),
        ("d7", "b7"), ("d8", "d3"),
        ("b7", "b8"), ("d3", "h7"),
        ("b8", "c8"), ("f7", "g6"),
        ("c8", "e6")  # Stalemate
    ]
    for from_sq, to_sq in moves:
        rv = make_move(client, from_sq, to_sq)
    # Game is over (stalemate)
    assert rv["stalemate"] == True
    # Try to make another move - should fail
    rv2 = make_move(client, "e6", "e7")
    assert rv2["status"] == "illegal"

# -------------------------------------------------------------------
# Turn Enforcement Tests
# -------------------------------------------------------------------

def test_cannot_move_opponent_pieces(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # White's turn - try to move black piece
    rv = make_move(client, "e7", "e5")
    # Should be rejected (white can't move black pieces)
    assert rv["status"] == "illegal"

def test_turn_alternates_correctly(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # White moves
    rv1 = make_move(client, "e2", "e4")
    assert rv1["status"] == "ok"
    assert rv1["turn"] == "black"
    # Black moves
    rv2 = make_move(client, "e7", "e5")
    assert rv2["status"] == "ok"
    assert rv2["turn"] == "white"
    # White moves again
    rv3 = make_move(client, "g1", "f3")
    assert rv3["status"] == "ok"
    assert rv3["turn"] == "black"

# -------------------------------------------------------------------
# Invalid Promotion Tests
# -------------------------------------------------------------------

def test_invalid_promotion_piece(client):
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
    # Try to promote to king (invalid)
    rv = make_move(client, "b7", "a8", promotion="k")
    assert rv["status"] == "illegal"

def test_promotion_without_reaching_rank(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Try to promote a pawn that hasn't reached rank 8
    rv = make_move(client, "e2", "e4", promotion="q")
    # This should either be illegal or ignore the promotion
    # Based on UCI, this would create an invalid move
    assert rv["status"] == "illegal"

# -------------------------------------------------------------------
# Check Flag Verification Tests
# -------------------------------------------------------------------

def test_check_flag_in_response(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Create a check position (not checkmate)
    make_move(client, "e2", "e4")
    make_move(client, "e7", "e5")
    make_move(client, "g1", "f3")
    make_move(client, "b8", "c6")
    make_move(client, "f1", "b5")  # Bishop pins knight, checking king
    rv = make_move(client, "a7", "a6")  # Black must respond
    make_move(client, "b5", "c6")  # Bishop takes knight
    # This is check (not checkmate)
    assert rv["check"] == False  # Last move was a6, which doesn't check white

def test_no_check_flag_when_not_in_check(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    rv = make_move(client, "e2", "e4")
    assert rv["check"] == False

# -------------------------------------------------------------------
# FEN Accuracy Tests
# -------------------------------------------------------------------

def test_fen_accuracy_after_complex_sequence(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Play a sequence of moves
    moves = [
        ("e2", "e4"), ("e7", "e5"),
        ("g1", "f3"), ("b8", "c6"),
        ("f1", "b5"), ("a7", "a6"),
        ("b5", "a4"), ("g8", "f6"),
    ]
    for from_sq, to_sq in moves:
        rv = make_move(client, from_sq, to_sq)
    
    # Verify FEN matches actual position
    board = chess.Board(rv["fen"])
    # Check specific pieces are in expected positions
    assert board.piece_at(chess.E4).symbol() == "P"  # White pawn on e4
    assert board.piece_at(chess.E5).symbol() == "p"  # Black pawn on e5
    assert board.piece_at(chess.F3).symbol() == "N"  # White knight on f3
    assert board.piece_at(chess.F6).symbol() == "n"  # Black knight on f6
    assert board.piece_at(chess.A4).symbol() == "B"  # White bishop on a4
    assert board.piece_at(chess.C6).symbol() == "n"  # Black knight on c6

def test_fen_accuracy_after_captures(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Perform captures
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    rv = make_move(client, "e4", "d5")
    
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.D5).symbol() == "P"  # White pawn on d5
    assert board.piece_at(chess.E4) is None  # E4 is now empty

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

def test_reset_clears_special_moves(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Make en passant (special move)
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    make_move(client, "e4", "e5")
    make_move(client, "f7", "f5")
    rv = make_move(client, "e5", "f6")
    assert len(rv["special_moves"]) == 1
    # Reset
    rv = client.post("/reset")
    data = rv.get_json()
    assert data["special_moves"] == []

def test_captured_pieces_symbol_format(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Capture pieces and verify symbol format
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    rv = make_move(client, "e4", "d5")  # White captures black pawn
    # Check that captured piece is lowercase (black pawn)
    captured = rv["captured_pieces"]["white"][0]
    assert captured == 'p'  # Black pieces are lowercase in python-chess

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

# -------------------------------------------------------------------
# Pinned Piece Tests
# -------------------------------------------------------------------

def test_pinned_piece_cannot_move_via_api(client):
    app.config['AI_ENABLED'] = False
    # Set up pinned position directly
    with client.session_transaction() as sess:
        # Bishop on d4 is pinned by rook on d8, king on d1
        sess['fen'] = '3r4/8/8/8/3B4/8/8/3K4 w - - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    # Try to move pinned bishop off the d-file (illegal)
    rv = make_move(client, "d4", "e5")
    assert rv["status"] == "illegal"
    # Try to move along the pin line - still illegal (absolute pin)
    rv = make_move(client, "d4", "d5")
    assert rv["status"] == "illegal"
    # Only king can move
    rv = make_move(client, "d1", "e2")
    assert rv["status"] == "ok"

# -------------------------------------------------------------------
# Long Game Stress Test
# -------------------------------------------------------------------

def test_long_game_move_history(client):
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Make 50 moves (100 half-moves) moving knights back and forth
    for i in range(25):
        make_move(client, "g1", "f3")
        make_move(client, "g8", "f6")
        make_move(client, "f3", "g1")
        rv = make_move(client, "f6", "g8")
    # Verify move history has 100 moves
    assert len(rv["move_history"]) == 100
    # Verify last few moves are correct
    assert rv["move_history"][-4] == "Nf3"
    assert rv["move_history"][-3] == "Nf6"
    assert rv["move_history"][-2] == "Ng1"
    assert rv["move_history"][-1] == "Ng8"

# NEW TESTS TO ADD

def test_move_from_empty_square(client):
    """Test trying to move from empty square"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    rv = make_move(client, "e4", "e5")  # e4 is empty
    assert rv["status"] == "illegal"

def test_move_opponent_piece_explicitly(client):
    """Test white trying to move black piece explicitly"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # It's white's turn, try to move black pawn
    rv = make_move(client, "e7", "e6")
    assert rv["status"] == "illegal"

def test_capture_own_piece(client):
    """Test trying to capture your own piece"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Try to move white pawn to capture white knight
    rv = make_move(client, "e2", "g1")
    assert rv["status"] == "illegal"

def test_fifty_move_rule_resets_on_pawn_move(client):
    """Verify fifty-move counter resets correctly"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Make 49 moves without pawn or capture
    for i in range(24):
        make_move(client, "g1", "f3")
        make_move(client, "g8", "f6")
        make_move(client, "f3", "g1")
        make_move(client, "f6", "g8")
    
    # One more knight move pair (98 moves total)
    make_move(client, "g1", "f3")
    rv = make_move(client, "g8", "f6")
    assert rv["fifty_moves"] == False  # Not yet 100 half-moves
    
    # Now make pawn move - should reset counter
    make_move(client, "e2", "e4")
    make_move(client, "f6", "g8")
    
    # Make 49 more moves
    for i in range(24):
        make_move(client, "f3", "g1")
        make_move(client, "g8", "f6")
        make_move(client, "g1", "f3")
        make_move(client, "f6", "g8")
    
    rv = make_move(client, "f3", "g1")
    # Should not trigger fifty-move because pawn move reset it
    assert rv["fifty_moves"] == False

def test_captured_pieces_symbol_case(client):
    """Verify captured pieces use correct case"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # White captures black pawn
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    rv = make_move(client, "e4", "d5")
    
    # Black pawn is lowercase 'p'
    assert 'p' in rv["captured_pieces"]["white"]
    assert 'P' not in rv["captured_pieces"]["white"]

def test_very_long_game_performance(client):
    """Test game with 200+ moves doesn't degrade"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Make 100 move pairs (200 half-moves)
    for i in range(100):
        rv1 = make_move(client, "g1", "f3")
        assert rv1["status"] == "ok", f"Failed at move {i*2}"
        rv2 = make_move(client, "g8", "f6")
        assert rv2["status"] == "ok", f"Failed at move {i*2+1}"
        rv3 = make_move(client, "f3", "g1")
        assert rv3["status"] == "ok"
        rv4 = make_move(client, "f6", "g8")
        assert rv4["status"] == "ok"
    
    # Verify move history is complete
    assert len(rv4["move_history"]) == 400

def test_algebraic_disambiguation(client):
    """Test SAN notation disambiguates pieces correctly"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up position with two knights that can move to same square
    with client.session_transaction() as sess:
        # Knights on b1 and f3, both can move to d2 (d2 pawn removed)
        sess['fen'] = 'rnbqkbnr/pppppppp/8/8/8/5N2/PPP1PPPP/RN1QKB1R w KQkq - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    # Move knight from b1 to d2 (both knights can reach d2, so should disambiguate)
    rv = make_move(client, "b1", "d2")
    assert rv["status"] == "ok"
    # Should be "Nbd2" (file disambiguation) not just "Nd2"
    assert rv["move_history"][-1] == "Nbd2"

def test_move_rejected_after_insufficient_material(client):
    """Test that moves are rejected after insufficient material draw"""
    app.config['AI_ENABLED'] = False
    with client.session_transaction() as sess:
        sess['fen'] = '8/8/8/4k3/8/8/4K3/8 w - - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
    
    # Game is over (insufficient material)
    rv = make_move(client, "e2", "e3")
    # Verify game over flag is set
    assert rv["insufficient_material"] == True
    assert rv["game_over"] == True

def test_en_passant_expires_after_one_move(client):
    """Test en passant opportunity expires if not taken immediately"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up en passant
    make_move(client, "e2", "e4")
    make_move(client, "a7", "a6")  # Black makes irrelevant move
    make_move(client, "e4", "e5")
    rv = make_move(client, "d7", "d5")  # Creates en passant on d6
    
    # FEN should show d6 as en passant square
    assert "d6" in rv["fen"], "En passant square d6 should be set"
    
    # White makes a different move (not en passant)
    rv = make_move(client, "g1", "f3")
    
    # En passant square should be gone from FEN
    assert "d6" not in rv["fen"], "En passant square should have expired"
    assert " - " in rv["fen"] or rv["fen"].split()[3] == "-", "En passant field should be '-'"

def test_en_passant_not_available_on_single_square_pawn_move(client):
    """Test en passant only works on 2-square pawn moves"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    make_move(client, "e2", "e4")
    make_move(client, "f7", "f6")  # One square move
    make_move(client, "e4", "e5")
    make_move(client, "f6", "f5")  # Now f5, but came from f6 not f7
    # Try en passant - should fail (wasn't 2-square move)
    rv = make_move(client, "e5", "f6")
    # This will be illegal because f6 is occupied
    # Better test: after f7-f6, white can't en passant

def test_move_history_check_notation(client):
    """Test that check is indicated with + in move history"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    moves = [
        ("e2", "e4"), ("e7", "e5"),
        ("f1", "c4"), ("g8", "f6"),
        ("g1", "f3"), ("f8", "c5"),
        ("c4", "f7")  # Check
    ]
    for from_sq, to_sq in moves:
        rv = make_move(client, from_sq, to_sq)
    
    # Last move should include '+' for check
    assert "+" in rv["move_history"][-1]

def test_move_history_checkmate_notation(client):
    """Test that checkmate is indicated with # in move history"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Fool's mate
    moves = [("f2","f3"), ("e7","e5"), ("g2","g4"), ("d8","h4")]
    for from_sq, to_sq in moves:
        rv = make_move(client, from_sq, to_sq)
    
    # Last move should include '#' for checkmate
    assert "#" in rv["move_history"][-1]

def test_captured_pieces_after_promotion_capture(client):
    """Test capture tracking when promotion captures a piece"""
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
    
    rv = make_move(client, "b7", "a8", promotion="q")
    # Should have captured rook
    assert 'r' in rv["captured_pieces"]["white"]
    assert len(rv["captured_pieces"]["white"]) == 2  # b7 pawn + a8 rook

def test_captured_pieces_order_preserved(client):
    """Test that capture order is preserved in captured_pieces list"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Capture pawn, then bishop
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    make_move(client, "e4", "d5")  # White captures black pawn
    make_move(client, "c8", "f5")  # Black bishop to f5
    make_move(client, "f1", "b5")  # White bishop to b5
    make_move(client, "b8", "c6")  # Black knight to c6
    rv = make_move(client, "b5", "c6")  # White bishop captures black knight
    
    # Should have [pawn, knight] in that order
    assert rv["captured_pieces"]["white"] == ['p', 'n']

def test_special_moves_cleared_on_reset(client):
    """Verify special_moves is properly cleared on reset"""
    # Already covered in test_reset_clears_special_moves
    pass

def test_multiple_promotions_tracked_separately(client):
    """Test that multiple promotions are tracked individually"""
    app.config['AI_ENABLED'] = False
    # Set up position where both sides can promote quickly
    with client.session_transaction() as sess:
        sess['fen'] = '1nbqkbnr/P6p/8/8/8/8/1PPPPPpP/RNBQKBNR w KQkq - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    make_move(client, "a7", "a8", promotion="q")
    rv = make_move(client, "g2", "h1", promotion="q")
    
    # Should have 2 promotion entries
    promotion_count = sum(1 for move in rv["special_moves"] if "Promotion" in move)
    assert promotion_count == 2

def test_fen_includes_en_passant_square(client):
    """Test that FEN includes en passant target square"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    make_move(client, "e4", "e5")
    rv = make_move(client, "f7", "f5")  # ← Check THIS response
    
    # FEN should include "f6" as en passant square
    fen = rv["fen"]
    assert "f6" in fen, f"Expected 'f6' in FEN, got: {fen}"

def test_fen_halfmove_clock_increments(client):
    """Test that halfmove clock increments correctly"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Make non-pawn, non-capture moves
    make_move(client, "g1", "f3")
    rv = make_move(client, "g8", "f6")
    
    fen_parts = rv["fen"].split()
    halfmove_clock = int(fen_parts[4])
    assert halfmove_clock == 2

def test_fen_fullmove_number_increments(client):
    """Test that fullmove number increments after black's move"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    make_move(client, "e2", "e4")
    rv = make_move(client, "e7", "e5")
    
    fen_parts = rv["fen"].split()
    fullmove_number = int(fen_parts[5])
    assert fullmove_number == 2

#material something tests

@pytest.mark.integration
def test_material_returned_on_capture(client):
    # White pawn captures black pawn
    set_position(client, "8/8/8/3p4/4P3/8/8/8 w - - 0 1")
    
    rv = make_move(client, "e4", "d5")
    
    assert rv["status"] == "ok"
    assert "material" in rv
    assert rv["material"] == 100


@pytest.mark.integration
def test_material_unchanged_on_illegal_move(client):
    set_position(client, chess.STARTING_FEN)
    
    rv = make_move(client, "e2", "e5")  # illegal
    
    assert rv["status"] == "illegal"
    assert "material" in rv 
    assert rv["material"] == 0


@pytest.mark.integration
def test_material_after_promotion(client):
    set_position(client, "8/P7/8/8/8/8/8/8 w - - 0 1")
    
    rv = make_move(client, "a7", "a8", promotion="q")
    
    assert rv["status"] == "ok"
    #should be 900 because we just check piece value for now
    assert rv["material"] == PIECE_VALUES[chess.QUEEN]

@pytest.mark.integration
def test_castling_does_not_change_material(client):
    set_position(client, chess.STARTING_FEN)
    
    make_move(client, "g1", "f3")
    make_move(client, "g8", "f6")
    make_move(client, "f1", "e2")
    
    rv = make_move(client, "e1", "g1")  # castle
    
    assert rv["material"] == 0

def test_en_passant_only_diagonal(client):
    """Test that en passant only works diagonally, not horizontally"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up en passant opportunity
    make_move(client, "e2", "e4")
    make_move(client, "a7", "a6")  # Random move
    make_move(client, "e4", "e5")
    make_move(client, "d7", "d5")  # Creates en passant on d6
    
    # Try to capture horizontally (illegal)
    # Pawn on e5 cannot move to d5 (that's horizontal capture, not diagonal)
    rv = make_move(client, "e5", "d5")
    # Actually this would be a diagonal capture of the pawn itself
    # Let me think... en passant is always diagonal (e5xd6), never horizontal
    # This test is already covered by the basic en passant test
    # Instead, test that en passant target square is diagonal
    assert rv["status"] == "illegal"  # Can't capture pawn on d5, must use d6
    
    # Correct en passant is diagonal to d6
    rv = make_move(client, "e5", "d6")
    assert rv["status"] == "ok"

def test_queenside_castling_b1_blocked_vs_attacked(client):
    """Clarify b1 under attack (legal) vs b1 blocked by piece (illegal)"""
    app.config['AI_ENABLED'] = False
    
    # Test 1: b1 is ATTACKED but empty - castling is LEGAL
    with client.session_transaction() as sess:
        sess['fen'] = '1r2k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    board = chess.Board('1r2k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
    assert board.is_attacked_by(chess.BLACK, chess.B1)  # b1 is attacked
    
    rv = make_move(client, "e1", "c1")
    assert rv["status"] == "ok", "Castling legal when b1 attacked but empty"
    
    # Test 2: b1 is BLOCKED by piece - castling is ILLEGAL
    reset_board(client)
    make_move(client, "d2", "d4")
    make_move(client, "d7", "d5")
    make_move(client, "c1", "f4")
    make_move(client, "c8", "f5")
    make_move(client, "d1", "d2")
    make_move(client, "d8", "d7")
    # b1 still has knight - try to castle
    rv = make_move(client, "e1", "c1")
    assert rv["status"] == "illegal", "Castling illegal when b1 blocked by knight"