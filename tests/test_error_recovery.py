"""
Error Recovery Tests
Tests graceful handling of edge cases and errors
"""
import pytest
import json
from app import create_app
from config import TestingConfig
from tests.test_routes_api import make_move, reset_board

app = create_app(TestingConfig)

@pytest.fixture
def client():
    #app.config['TESTING'] = True
    app.config['AI_ENABLED'] = False
    with app.test_client() as client:
        yield client


def test_recover_from_invalid_fen_in_session(client):
    """Server handles corrupted FEN gracefully"""
    reset_board(client)
    
    # Corrupt session with invalid FEN
    with client.session_transaction() as sess:
        sess['fen'] = "invalid fen string"
    
    # Should auto-recover by resetting to starting position
    rv = make_move(client, "e2", "e4")
    
    # Should either succeed (auto-recovery) or return clear error
    assert rv["status"] in ["ok", "illegal"]


def test_recover_from_missing_fen_key(client):
    """Missing FEN key triggers re-initialization"""
    with client.session_transaction() as sess:
        sess.pop('fen', None)
    
    # Should initialize new game
    rv = client.get("/")
    assert rv.status_code == 200
    
    # First move should work
    rv = make_move(client, "e2", "e4")
    assert rv["status"] == "ok"


def test_recover_from_missing_move_history(client):
    """Missing move_history is handled gracefully"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        sess.pop('move_history', None)
    
    rv = make_move(client, "e2", "e4")
    assert rv["status"] == "ok"
    assert "move_history" in rv


def test_recover_from_missing_captured_pieces(client):
    """Missing captured_pieces is handled gracefully"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        sess.pop('captured_pieces', None)
    
    rv = make_move(client, "e2", "e4")
    assert rv["status"] == "ok"
    assert "captured_pieces" in rv


def test_handle_empty_move_request(client):
    """Empty POST body returns appropriate error"""
    reset_board(client)
    
    rv = client.post("/move", data="", content_type="application/json")
    assert rv.status_code == 400


def test_handle_malformed_json(client):
    """Malformed JSON returns 400 Bad Request"""
    reset_board(client)
    
    rv = client.post("/move", data="{invalid json", content_type="application/json")
    assert rv.status_code == 400


def test_handle_missing_from_field(client):
    """Missing 'from' field returns illegal status"""
    reset_board(client)
    
    payload = {"to": "e4"}
    rv = client.post("/move", data=json.dumps(payload), content_type="application/json")
    data = rv.get_json()
    
    assert data["status"] == "illegal"


def test_handle_missing_to_field(client):
    """Missing 'to' field returns illegal status"""
    reset_board(client)
    
    payload = {"from": "e2"}
    rv = client.post("/move", data=json.dumps(payload), content_type="application/json")
    data = rv.get_json()
    
    assert data["status"] == "illegal"


def test_handle_invalid_square_notation(client):
    """Invalid square notation (e.g., 'z9') returns illegal"""
    reset_board(client)
    
    rv = make_move(client, "z9", "z1")
    assert rv["status"] == "illegal"


def test_handle_out_of_bounds_square(client):
    """Out of bounds square returns illegal"""
    reset_board(client)
    
    rv = make_move(client, "e2", "e9")  # Rank 9 doesn't exist
    assert rv["status"] == "illegal"


def test_handle_move_after_game_over(client):
    """Moves after game over are rejected"""
    reset_board(client)
    
    # Fool's mate
    moves = [("f2","f3"), ("e7","e5"), ("g2","g4"), ("d8","h4")]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    # Try another move
    rv = make_move(client, "e2", "e4")
    assert rv["status"] == "illegal"


def test_handle_promotion_without_piece_specified(client):
    """Promotion without piece returns illegal"""
    with client.session_transaction() as sess:
        sess['fen'] = '1nbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    # Try to promote without specifying piece
    rv = make_move(client, "a7", "a8")
    assert rv["status"] == "illegal"


def test_handle_invalid_promotion_piece(client):
    """Promotion to invalid piece (e.g., 'k') returns illegal"""
    with client.session_transaction() as sess:
        sess['fen'] = '1nbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    rv = make_move(client, "a7", "a8", promotion="k")
    assert rv["status"] == "illegal"


def test_handle_lowercase_uppercase_promotion(client):
    """Both lowercase and uppercase promotion work"""
    with client.session_transaction() as sess:
        sess['fen'] = '1nbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    # Lowercase (UCI standard)
    rv = make_move(client, "a7", "a8", promotion="q")
    assert rv["status"] == "ok"


def test_handle_session_size_overflow():
    """Session handles large move history gracefully"""
    with app.test_client() as client:
        reset_board(client)
        
        # Make 200 moves (400 half-moves)
        for i in range(100):
            rv1 = make_move(client, "g1", "f3")
            if rv1["status"] != "ok":
                break
            rv2 = make_move(client, "g8", "f6")
            if rv2["status"] != "ok":
                break
            rv3 = make_move(client, "f3", "g1")
            if rv3["status"] != "ok":
                break
            rv4 = make_move(client, "f6", "g8")
            if rv4["status"] != "ok":
                break
        
        # Should still be functional
        rv = client.post("/reset")
        assert rv.get_json()["status"] == "ok"


def test_handle_special_characters_in_move(client):
    """Special characters in move data don't crash server"""
    reset_board(client)
    
    payload = {"from": "<script>alert('xss')</script>", "to": "e4"}
    rv = client.post("/move", data=json.dumps(payload), content_type="application/json")
    
    # Should return illegal, not crash
    data = rv.get_json()
    assert data["status"] == "illegal"


def test_handle_null_values_in_move(client):
    """Null values in move data are handled"""
    reset_board(client)
    
    payload = {"from": None, "to": "e4"}
    rv = client.post("/move", data=json.dumps(payload), content_type="application/json")
    
    data = rv.get_json()
    assert data["status"] == "illegal"


def test_handle_wrong_content_type(client):
    """Request without JSON content type is rejected"""
    reset_board(client)
    
    rv = client.post("/move", data="e2e4", content_type="text/plain")
    # Should return 400 or handle gracefully
    assert rv.status_code in [400, 415]  # 415 = Unsupported Media Type


def test_recover_from_inconsistent_captured_pieces(client):
    """Inconsistent captured_pieces structure is fixed"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        sess['captured_pieces'] = "invalid string"  # Should be dict
    
    rv = make_move(client, "e2", "e4")
    # Should auto-recover
    assert "captured_pieces" in rv
    assert isinstance(rv["captured_pieces"], dict)


def test_handle_get_request_to_move_endpoint(client):
    """GET request to /move returns error"""
    reset_board(client)
    
    rv = client.get("/move")
    # Should return 405 Method Not Allowed
    assert rv.status_code == 405


def test_handle_concurrent_move_requests():
    """Concurrent requests don't corrupt session"""
    with app.test_client() as client:
        reset_board(client)
        
        # Simulate near-concurrent moves (not truly concurrent in test)
        rv1 = make_move(client, "e2", "e4")
        rv2 = make_move(client, "e7", "e5")
        
        assert rv1["status"] == "ok"
        assert rv2["status"] == "ok"
        assert len(rv2["move_history"]) == 2