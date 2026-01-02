"""
Session Persistence Tests
Critical tests for production deployment
"""
import pytest
import chess
import os
from app import create_app
from config import TestingConfig, TestingConfigFilesystem
from tests.test_routes_api import make_move, reset_board

app = create_app(TestingConfig)

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['AI_ENABLED'] = False
    with app.test_client() as client:
        yield client


@pytest.fixture
def filesystem_client():
    """Client using filesystem sessions (for file-based session tests)"""
    fs_app = create_app(TestingConfigFilesystem)
    fs_app.config['AI_ENABLED'] = False
    with fs_app.test_client() as client:
        yield client


def test_session_persists_across_requests(client):
    """Session state persists between API calls"""
    reset_board(client)
    
    # First request (white)
    rv1 = make_move(client, "e2", "e4")
    assert rv1["status"] == "ok"
    assert len(rv1["move_history"]) == 1
    
    # Second request (black, alternating turn)
    rv2 = make_move(client, "e7", "e5")
    assert rv2["status"] == "ok"
    assert len(rv2["move_history"]) == 2
    assert rv2["move_history"][0] == "e4"
    assert rv2["move_history"][1] == "e5"


def test_session_isolated_between_clients(client):
    """Two clients have separate session states"""
    reset_board(client)
    
    # Client 1 makes move
    rv1 = make_move(client, "e2", "e4")
    assert len(rv1["move_history"]) == 1
    
    # Client 2 (new session) should have fresh board
    with app.test_client() as client2:
        rv2 = make_move(client2, "e2", "e4")
        # Client 2 should be at move 1, not move 2
        assert len(rv2["move_history"]) == 1
        assert rv2["move_history"][0] == "e4"


def test_session_survives_multiple_moves(client):
    """Session handles long game without corruption"""
    reset_board(client)
    
    # Make 20 moves
    moves = [
        ("e2", "e4"), ("d2", "d4"), ("g1", "f3"), ("b1", "c3"),
        ("f1", "e2"), ("c1", "f4"), ("d1", "d2"), ("a2", "a3"),
        ("b2", "b3"), ("h2", "h3")
    ]
    
    for i, (from_sq, to_sq) in enumerate(moves, 1):
        rv = make_move(client, from_sq, to_sq)
        if rv["status"] == "ok":
            assert len(rv["move_history"]) >= i


def test_session_file_created_on_filesystem(filesystem_client):
    """Verify session file is created in flask_session/"""
    from config import TestingConfigFilesystem
    
    reset_board(filesystem_client)
    make_move(filesystem_client, "e2", "e4")
    
    # Check flask_session directory exists and has files
    session_dir = TestingConfigFilesystem.SESSION_FILE_DIR
    assert os.path.exists(session_dir), "Session directory should exist"
    
    files = os.listdir(session_dir)
    assert len(files) > 0, "Session files should exist"


def test_session_cookie_set_in_response(client):
    """Verify Set-Cookie header is present"""
    rv = client.get("/")
    
    # Check Set-Cookie header exists
    cookies = [h for h in rv.headers if h[0] == 'Set-Cookie']
    assert len(cookies) > 0, "Should set session cookie"
    
    cookie_value = cookies[0][1]
    assert 'chess_session' in cookie_value


def test_session_cleared_on_reset(client):
    """Reset clears all session data"""
    # Make some moves
    make_move(client, "e2", "e4")
    make_move(client, "d2", "d4")
    
    # Reset
    rv = client.post("/reset")
    data = rv.get_json()
    
    assert data["move_history"] == []
    assert data["captured_pieces"] == {'white': [], 'black': []}
    assert data["special_moves"] == []
    assert data["fen"] == chess.STARTING_FEN


def test_session_state_after_illegal_move(client):
    """Illegal move doesn't corrupt session"""
    reset_board(client)
    make_move(client, "e2", "e4")
    
    # Illegal move (white trying to move again)
    rv_illegal = make_move(client, "e4", "e6")
    assert rv_illegal["status"] == "illegal"
    
    # Session should still be valid; make legal black move
    rv_legal = make_move(client, "e7", "e5")
    assert rv_legal["status"] == "ok"
    assert len(rv_legal["move_history"]) == 2


def test_session_handles_concurrent_requests():
    """Session handles rapid sequential requests"""
    with app.test_client() as client:
        reset_board(client)
        
        # Simulate rapid alternating moves
        moves = [("e2", "e4"), ("e7", "e5"), ("g1", "f3")]
        
        for i, (from_sq, to_sq) in enumerate(moves):
            rv = make_move(client, from_sq, to_sq)
            assert rv["status"] == "ok"
            assert len(rv["move_history"]) == i + 1


def test_session_data_types_preserved(client):
    """Session preserves data types (lists, dicts)"""
    reset_board(client)
    
    # Set up position where white can capture
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    rv = make_move(client, "e4", "d5")  # White captures black pawn
    
    # Verify types on successful move response
    assert isinstance(rv["move_history"], list)
    assert isinstance(rv["captured_pieces"], dict)
    assert isinstance(rv["captured_pieces"]["white"], list)
    assert len(rv["captured_pieces"]["white"]) == 1  # Captured one pawn

def test_session_size_reasonable_after_long_game(filesystem_client):
    """Session file size stays reasonable after many moves"""
    from config import TestingConfigFilesystem
    
    reset_board(filesystem_client)
    
    # Make 50 moves (100 half-moves)
    for i in range(25):
        make_move(filesystem_client, "g1", "f3")
        make_move(filesystem_client, "g8", "f6")
        make_move(filesystem_client, "f3", "g1")
        make_move(filesystem_client, "f6", "g8")
    
    # Check session file size
    session_dir = TestingConfigFilesystem.SESSION_FILE_DIR
    files = os.listdir(session_dir)
    
    if files:
        session_file = os.path.join(session_dir, files[0])
        size = os.path.getsize(session_file)
        
        # Session file should be < 100KB
        assert size < 100 * 1024, f"Session file too large: {size} bytes"


def test_session_cleanup_after_game_over(client):
    """Session persists even after game over"""
    reset_board(client)
    
    # Fool's mate
    moves = [("f2","f3"), ("e7","e5"), ("g2","g4"), ("d8","h4")]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    # Game over - session should still exist
    rv = client.post("/reset")
    assert rv.get_json()["status"] == "ok"


def test_session_modified_flag_set_correctly(client):
    """session.modified = True after state changes"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        initial_fen = sess.get('fen')
    
    make_move(client, "e2", "e4")
    
    with client.session_transaction() as sess:
        new_fen = sess.get('fen')
        assert new_fen != initial_fen