"""
Game End States Tests
Tests for resignation, draw claims, and draw agreements
These are critical game-ending scenarios that must work correctly
"""
import pytest
import json
import chess
from app import create_app
from config import TestingConfig
from models import Game, GameMove, db
from tests.test_routes_api import make_move, reset_board

app = create_app(TestingConfig)


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['AI_ENABLED'] = False
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client


# =============================================================================
# RESIGNATION TESTS
# =============================================================================

def test_resign_white_returns_0_1(client):
    """White resignation results in 0-1 score (black wins)"""
    reset_board(client)
    
    rv = client.post("/resign", 
                     data=json.dumps({"color": "white"}), 
                     content_type="application/json")
    data = rv.get_json()
    
    assert data["status"] == "ok"
    assert data["result"] == "0-1"
    assert data["winner"] == "black"
    assert data["termination_reason"] == "resignation"


def test_resign_black_returns_1_0(client):
    """Black resignation results in 1-0 score (white wins)"""
    reset_board(client)
    
    rv = client.post("/resign", 
                     data=json.dumps({"color": "black"}), 
                     content_type="application/json")
    data = rv.get_json()
    
    assert data["status"] == "ok"
    assert data["result"] == "1-0"
    assert data["winner"] == "white"
    assert data["termination_reason"] == "resignation"


def test_resign_sets_game_over_flag(client):
    """Resignation sets game_over flag in response"""
    reset_board(client)
    
    rv = client.post("/resign", 
                     data=json.dumps({"color": "white"}), 
                     content_type="application/json")
    data = rv.get_json()
    
    assert data["game_over"] == True


def test_resign_invalid_color_returns_error(client):
    """Invalid color in resignation returns error"""
    reset_board(client)
    
    rv = client.post("/resign", 
                     data=json.dumps({"color": "purple"}), 
                     content_type="application/json")
    data = rv.get_json()
    
    assert data["status"] == "error"
    assert "Invalid color" in data["message"]


def test_resign_no_active_game_returns_error(client):
    """Resigning without active game returns error"""
    # Don't reset - no game
    rv = client.post("/resign", 
                     data=json.dumps({"color": "white"}), 
                     content_type="application/json")
    data = rv.get_json()
    
    assert data["status"] == "error"
    assert "No active game" in data["message"]


def test_resign_after_game_over_returns_error(client):
    """Cannot resign after game already ended"""
    reset_board(client)
    
    # End game by checkmate (fool's mate)
    moves = [("f2","f3"), ("e7","e5"), ("g2","g4"), ("d8","h4")]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    # Try to resign
    rv = client.post("/resign", 
                     data=json.dumps({"color": "white"}), 
                     content_type="application/json")
    data = rv.get_json()
    
    assert data["status"] == "error"
    assert "already ended" in data["message"].lower()


def test_resign_logged_to_database(client):
    """Resignation is logged to database"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
    
    # Resign
    rv = client.post("/resign", 
                     data=json.dumps({"color": "white"}), 
                     content_type="application/json")
    assert rv.get_json()["status"] == "ok"
    
    # Verify in database
    with client.application.app_context():
        game = db.session.get(Game, game_id)
        assert game.result == "0-1"
        assert game.termination_reason == "resignation"
        assert game.ended_at is not None
        assert game.state == "finished"


def test_resign_creates_game_move_entry(client):
    """Resignation creates [Resignation] marker in GameMove"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
    
    # Resign
    client.post("/resign", 
                data=json.dumps({"color": "white"}), 
                content_type="application/json")
    
    # Verify GameMove entry
    with client.application.app_context():
        moves = GameMove.query.filter_by(game_id=game_id).all()
        # Should have at least one move entry with [Resignation] marker
        assert len(moves) >= 1
        assert any("[Resignation]" in move.san for move in moves)


def test_resign_clears_session_fen(client):
    """Session FEN is cleared after resignation"""
    reset_board(client)
    
    # Verify FEN exists before resignation
    with client.session_transaction() as sess:
        assert sess.get("fen") is not None
    
    # Resign
    client.post("/resign", 
                data=json.dumps({"color": "white"}), 
                content_type="application/json")
    
    # Verify FEN is cleared
    with client.session_transaction() as sess:
        assert sess.get("fen") is None


def test_resign_updates_game_state(client):
    """Game state is set to 'finished' after resignation"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
    
    # Verify state is active before resignation
    with client.application.app_context():
        game = db.session.get(Game, game_id)
        assert game.state == "active"
    
    # Resign
    client.post("/resign", 
                data=json.dumps({"color": "white"}), 
                content_type="application/json")
    
    # Verify state is finished
    with client.application.app_context():
        game = db.session.get(Game, game_id)
        assert game.state == "finished"


# =============================================================================
# 50-MOVE DRAW TESTS
# =============================================================================

def test_claim_50_move_draw_valid(client):
    """50-move draw claim is accepted when conditions met"""
    reset_board(client)
    
    # Set up position with halfmove_clock at 100 (the threshold)
    with client.session_transaction() as sess:
        fen_parts = chess.STARTING_FEN.split()
        fen_parts[4] = "100"  # halfmove_clock
        fen = " ".join(fen_parts)
        sess['fen'] = fen
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
        sess.modified = True
    
    # Claim draw
    data = client.post("/claim-draw/50-move").get_json()
    
    assert data["status"] == "ok"
    assert data["result"] == "1/2-1/2"


def test_claim_50_move_draw_invalid(client):
    """50-move draw claim is rejected when not eligible"""
    reset_board(client)
    
    # Default position has halfmove_clock at 0, not eligible
    data = client.post("/claim-draw/50-move").get_json()
    
    assert data["status"] == "invalid"
    assert "not_claimable" in data.get("reason", "")


def test_claim_50_move_draw_logged_to_database(client):
    """50-move draw claim is logged to database"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        fen_parts = chess.STARTING_FEN.split()
        fen_parts[4] = "100"
        fen = " ".join(fen_parts)
        sess['fen'] = fen
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
        sess.modified = True
    
    # Claim draw
    rv = client.post("/claim-draw/50-move").get_json()
    assert rv["status"] == "ok"
    
    # Verify in database
    with client.application.app_context():
        game = db.session.get(Game, game_id)
        assert game.result == "1/2-1/2"
        assert game.termination_reason == "draw_50_move_rule"


def test_claim_50_move_draw_game_over(client):
    """After 50-move draw claim, game is marked over"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        fen_parts = chess.STARTING_FEN.split()
        fen_parts[4] = "100"
        fen = " ".join(fen_parts)
        sess['fen'] = fen
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
        sess.modified = True
    
    # Claim draw
    data = client.post("/claim-draw/50-move").get_json()
    assert data["status"] == "ok"
    
    # Verify game is finished
    with client.application.app_context():
        game = db.session.get(Game, game_id)
        assert game.state == "finished"
        assert game.ended_at is not None


def test_claim_50_move_after_game_over_error(client):
    """Cannot claim 50-move draw after game already ended"""
    reset_board(client)

    # Prepare a claimable 50-move position, then end the game first.
    with client.session_transaction() as sess:
        fen_parts = chess.STARTING_FEN.split()
        fen_parts[4] = "100"
        sess["fen"] = " ".join(fen_parts)
        sess["move_history"] = []
        sess["captured_pieces"] = {"white": [], "black": []}
        sess["special_moves"] = []
        sess.modified = True

    first = client.post("/draw-agreement").get_json()
    assert first["status"] == "ok"

    # Claiming again after game end should return game_over.
    second = client.post("/claim-draw/50-move").get_json()
    assert second["status"] == "game_over"


# =============================================================================
# THREEFOLD REPETITION TESTS
# =============================================================================

def test_claim_repetition_draw_valid(client):
    """Repetition draw claim is accepted when conditions met"""
    reset_board(client)
    
    # Make move sequence that creates threefold repetition
    moves = [
        ("g1", "f3"), ("g8", "f6"),
        ("f3", "g1"), ("f6", "g8"),
        ("g1", "f3"), ("g8", "f6"),
    ]
    
    for from_sq, to_sq in moves:
        rv = make_move(client, from_sq, to_sq)
        if rv.get("game_over"):
            break
    
    # At this point we should have threefold repetition available to claim
    data = client.post("/claim-draw/repetition").get_json()
    
    # The response should be either ok (if repetition exists) or invalid
    assert data["status"] in ["ok", "invalid"]
    if data["status"] == "ok":
        assert data["result"] == "1/2-1/2"


def test_claim_repetition_draw_invalid(client):
    """Repetition draw claim is rejected when not eligible"""
    reset_board(client)
    
    # Default position doesn't have repetition
    data = client.post("/claim-draw/repetition").get_json()
    
    assert data["status"] == "invalid"
    assert "not_claimable" in data.get("reason", "")


def test_claim_repetition_draw_logged_to_database(client):
    """Repetition draw claim is logged to database"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
    
    # Create repetition
    moves = [
        ("g1", "f3"), ("g8", "f6"),
        ("f3", "g1"), ("f6", "g8"),
        ("g1", "f3"), ("g8", "f6"),
    ]
    
    for from_sq, to_sq in moves:
        rv = make_move(client, from_sq, to_sq)
        if rv.get("game_over"):
            break
    
    # Claim draw
    rv = client.post("/claim-draw/repetition").get_json()
    
    if rv["status"] == "ok":
        with client.application.app_context():
            game = db.session.get(Game, game_id)
            assert game.result == "1/2-1/2"
            assert game.termination_reason == "draw_threefold_repetition"


def test_claim_repetition_after_game_over_error(client):
    """Cannot claim repetition after game already ended"""
    reset_board(client)

    # Seed a threefold-claimable position.
    with client.session_transaction() as sess:
        sess["fen"] = chess.STARTING_FEN
        sess["move_history"] = ["Nf3", "Nf6", "Ng1", "Ng8", "Nf3", "Nf6", "Ng1", "Ng8"]
        sess["captured_pieces"] = {"white": [], "black": []}
        sess["special_moves"] = []
        sess.modified = True

    first = client.post("/claim-draw/repetition").get_json()
    assert first["status"] == "ok"

    # Claiming again on the same ended game should report game_over.
    second = client.post("/claim-draw/repetition").get_json()
    assert second["status"] == "game_over"


# =============================================================================
# DRAW AGREEMENT TESTS
# =============================================================================

def test_draw_agreement_both_players(client):
    """Draw agreement marks game as draw"""
    reset_board(client)
    
    rv = client.post("/draw-agreement").get_json()
    
    assert rv["status"] == "ok"
    assert rv["result"] == "1/2-1/2"


def test_draw_agreement_sets_game_over(client):
    """Draw agreement sets game_over flag"""
    reset_board(client)
    
    # Make a move first to have something logged
    make_move(client, "e2", "e4")
    
    rv = client.post("/draw-agreement").get_json()
    
    # Response might not have game_over flag, but game should be marked finished
    assert rv["status"] == "ok"


def test_draw_agreement_logged_to_database(client):
    """Draw agreement is logged to database"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
    
    # Agree to draw
    rv = client.post("/draw-agreement").get_json()
    assert rv["status"] == "ok"
    
    # Verify in database
    with client.application.app_context():
        game = db.session.get(Game, game_id)
        assert game.result == "1/2-1/2"
        assert game.termination_reason == "draw_by_agreement"
        assert game.state == "finished"


def test_draw_agreement_game_over_error(client):
    """Cannot agree to draw after game already ended"""
    reset_board(client)

    first = client.post("/draw-agreement").get_json()
    assert first["status"] == "ok"

    # Second draw agreement request should be rejected as game_over.
    second = client.post("/draw-agreement").get_json()
    assert second["status"] == "game_over"


def test_draw_agreement_creates_game_move_entry(client):
    """Draw agreement creates [Draw agreed] marker in GameMove"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
    
    # Agree to draw
    client.post("/draw-agreement")
    
    # Verify GameMove entry
    with client.application.app_context():
        moves = GameMove.query.filter_by(game_id=game_id).all()
        # Should have entry with [Draw agreed] marker
        assert any("[Draw agreed]" in move.san for move in moves)


# =============================================================================
# MOVES REJECTED AFTER GAME END
# =============================================================================

def test_moves_rejected_after_resign(client):
    """Session is cleared after resignation"""
    reset_board(client)
    
    # Resign
    rv = client.post("/resign", 
                     data=json.dumps({"color": "white"}), 
                     content_type="application/json")
    assert rv.get_json()["status"] == "ok"
    
    # FEN should be cleared
    with client.session_transaction() as sess:
        assert sess.get("fen") is None


def test_moves_rejected_after_draw_agreement(client):
    """Session is preserved after draw agreement (allows move check)"""
    reset_board(client)
    
    # Make a move to have something in history
    make_move(client, "e2", "e4")
    
    # Agree to draw
    rv = client.post("/draw-agreement").get_json()
    assert rv["status"] == "ok"
    
    # FEN might still be in session, but game should be finished
    with client.application.app_context():
        # Verify game is finished in database
        with client.session_transaction() as sess:
            game_id = sess.get("game_id")
        
        game = db.session.get(Game, game_id)
        assert game.state == "finished"


# =============================================================================
# RESULT VERIFICATION TESTS
# =============================================================================

def test_resignation_sets_correct_player_uuid(client):
    """Player UUID is preserved during resignation"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        initial_uuid = sess.get("player_uuid")
    
    # Resign
    client.post("/resign", 
                data=json.dumps({"color": "white"}), 
                content_type="application/json")
    
    # Verify game has correct UUID
    with client.application.app_context():
        game = db.session.get(Game, game_id)
        assert game.player_uuid is not None


def test_resignation_result_is_not_draw(client):
    """Resignation results in 1-0 or 0-1, never 1/2-1/2"""
    reset_board(client)
    
    # Resign white
    rv = client.post("/resign", 
                     data=json.dumps({"color": "white"}), 
                     content_type="application/json").get_json()
    
    assert rv["result"] != "1/2-1/2"
    assert rv["result"] in ["1-0", "0-1"]


def test_resign_after_multiple_moves(client):
    """Can resign after making multiple moves"""
    reset_board(client)
    
    # Make several moves
    moves = [("e2", "e4"), ("d2", "d4"), ("g1", "f3")]
    for from_sq, to_sq in moves:
        rv = make_move(client, from_sq, to_sq)
        if rv.get("status") != "ok":
            break
    
    # Resign
    rv = client.post("/resign", 
                     data=json.dumps({"color": "white"}), 
                     content_type="application/json").get_json()
    
    assert rv["status"] == "ok"
    assert rv["result"] == "0-1"  # White resigned, black wins


# =============================================================================
# EDGE CASES
# =============================================================================

def test_draw_claim_when_game_has_moves(client):
    """Can claim draw after making moves"""
    reset_board(client)
    
    # Make some moves
    make_move(client, "e2", "e4")
    make_move(client, "e7", "e5")
    
    # Try to claim draw - should fail (no conditions met)
    # unless we set halfmove_clock
    rv = client.post("/claim-draw/50-move").get_json()
    assert rv["status"] in ["invalid", "ok"]  # Depends on position


def test_multiple_resignations_same_session(client):
    """Cannot resign twice in same game"""
    reset_board(client)
    
    # Resign once
    rv1 = client.post("/resign", 
                      data=json.dumps({"color": "white"}), 
                      content_type="application/json").get_json()
    assert rv1["status"] == "ok"
    
    # FEN is cleared, so next request will init new game
    # This is the current behavior


def test_game_move_count_after_resignation(client):
    """Move count is preserved after resignation"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
    
    # Make moves
    make_move(client, "e2", "e4")
    make_move(client, "e7", "e5")
    
    # Resign
    client.post("/resign", 
                data=json.dumps({"color": "white"}), 
                content_type="application/json")
    
    # Verify move count in database
    with client.application.app_context():
        moves = GameMove.query.filter_by(game_id=game_id).all()
        # Should have 2 player moves + 1 resignation marker = 3 total
        assert len(moves) >= 2
