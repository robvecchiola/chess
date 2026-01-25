"""
Database Model Tests
Tests for Game and GameMove models, database logging
"""
import pytest
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
            db.create_all()  # Ensure tables exist
        yield client

def test_game_creation_on_init(client):
    """Game is created when init_game is called"""
    with client.application.test_request_context():
        # Count games before
        games_before = Game.query.count()
        
        # Call init_game
        from helpers import init_game
        init_game()
        
        # Should have created one more game
        games_after = Game.query.count()
        assert games_after == games_before + 1
        
        # Get the latest game
        game = Game.query.order_by(Game.id.desc()).first()
        assert game.ai_enabled == True  # Default
        assert game.ended_at is None

def test_game_move_logging_player_move(client):
    """Player moves are logged to database"""
    reset_board(client)
    
    # Make a move
    rv = make_move(client, "e2", "e4")
    assert rv["status"] == "ok"
    
    # Get current game ID and filter moves
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        moves = GameMove.query.filter_by(game_id=game_id).all()
        assert len(moves) == 1
        move = moves[0]
        assert move.color == "white"
        assert move.san == "e4"
        assert move.uci == "e2e4"
        assert move.fen_after == rv["fen"]

def test_game_move_logging_ai_move(client):
    """AI moves are logged to database"""
    app.config['AI_ENABLED'] = True
    reset_board(client)
    
    # Make player move
    rv = make_move(client, "e2", "e4")
    assert rv["status"] == "ok"
    
    # Make AI move
    ai_rv = client.post("/ai-move")
    assert ai_rv.status_code == 200
    
    # Get current game ID and filter moves
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        moves = GameMove.query.filter_by(game_id=game_id).all()
        assert len(moves) == 2  # Player + AI
        
        player_move = moves[0]
        ai_move = moves[1]
        
        assert player_move.color == "white"
        assert ai_move.color == "black"

def test_game_finalization_on_checkmate(client):
    """Game is finalized when checkmate occurs"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Fool's mate
    moves = [("f2","f3"), ("e7","e5"), ("g2","g4"), ("d8","h4")]
    for from_sq, to_sq in moves:
        rv = make_move(client, from_sq, to_sq)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        assert game.ended_at is not None
        assert game.result == "0-1"
        assert game.termination_reason == "checkmate"

def test_game_finalization_on_resignation(client):
    """Game is finalized when player resigns"""
    reset_board(client)
    
    # Resign as white
    rv = client.post("/resign", 
                     data='{"color": "white"}', 
                     content_type="application/json")
    data = rv.get_json()
    assert data["status"] == "ok"
    assert data["result"] == "0-1"
    assert data["termination_reason"] == "resignation"
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        assert game.ended_at is not None
        assert game.result == "0-1"
        assert game.termination_reason == "resignation"

def test_multiple_games_isolated(client):
    """Multiple games don't interfere"""
    # Count games before test
    with app.app_context():
        games_before = Game.query.count()
    
    reset_board(client)
    make_move(client, "e2", "e4")
    
    # New client session
    with app.test_client() as client2:
        reset_board(client2)
        make_move(client2, "d2", "d4")
        
        with app.app_context():
            games_after = Game.query.count()
            assert games_after == games_before + 2
            
            # Get the last two games
            games = Game.query.order_by(Game.id.desc()).limit(2).all()
            game1, game2 = games
            
            # Each has one move
            moves1 = GameMove.query.filter_by(game_id=game1.id).all()
            moves2 = GameMove.query.filter_by(game_id=game2.id).all()
            assert len(moves1) == 1
            assert len(moves2) == 1

def test_promotion_logged_correctly(client):
    """Promotion moves are logged with correct SAN"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up promotion
    moves = [
        ("a2", "a4"), ("h7", "h6"),
        ("a4", "a5"), ("h6", "h5"),
        ("a5", "a6"), ("h5", "h4"),
        ("a6", "b7"), ("h4", "h3"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    rv = make_move(client, "b7", "a8", promotion="q")
    
    # Get current game ID and find the promotion move
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        move = GameMove.query.filter_by(game_id=game_id, color="white").order_by(GameMove.move_number.desc()).first()
        assert "a8=Q" in move.san or move.san.endswith("=Q")

def test_castling_logged_correctly(client):
    """Castling moves are logged correctly"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up castling
    moves = [
        ("e2", "e4"), ("e7", "e5"),
        ("g1", "f3"), ("g8", "f6"),
        ("f1", "e2"), ("f8", "e7"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    rv = make_move(client, "e1", "g1")
    
    # Get current game ID and find the castling move
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        move = GameMove.query.filter_by(game_id=game_id, color="white").order_by(GameMove.move_number.desc()).first()
        assert move.san == "O-O"
    assert move.uci == "e1g1"


# =============================================================================
# ADDITIONAL DATABASE TESTS - NEW
# =============================================================================

def test_game_move_fen_after_accuracy(client):
    """GameMove.fen_after stores the correct board state"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Make move and capture its FEN
    rv = make_move(client, "e2", "e4")
    fen_after_first = rv["fen"]
    
    # Get the move from database
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        move = GameMove.query.filter_by(game_id=game_id, move_number=1).first()
        
        assert move.fen_after == fen_after_first


def test_game_last_activity_updates_on_move(client):
    """Game.last_activity_at is updated on each move"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        initial_activity = game.last_activity_at
    
    import time
    time.sleep(0.1)  # Ensure time difference
    
    # Make a move
    make_move(client, "e2", "e4")
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        updated_activity = game.last_activity_at
    
    assert updated_activity > initial_activity


def test_resignation_logged_with_marker(client):
    """Resignation creates GameMove with [Resignation] marker"""
    reset_board(client)
    
    client.post("/resign", 
                data='{"color": "white"}', 
                content_type="application/json")
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        # Find the resignation move
        move = GameMove.query.filter_by(game_id=game_id).order_by(GameMove.move_number.desc()).first()
        
        assert "[Resignation]" in move.san


def test_draw_claim_logged_with_marker(client):
    """50-move draw claim creates GameMove with marker"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set position where 50-move rule applies (halfmove_clock = 100 means 50 moves without pawn/capture)
    with client.session_transaction() as sess:
        sess['fen'] = '8/8/8/4k3/8/8/4K2N/8 w - - 100 50'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    client.post("/claim-draw/50-move")
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        move = GameMove.query.filter_by(game_id=game_id).order_by(GameMove.move_number.desc()).first()
        
        assert "[Draw claimed: 50-move rule]" in move.san


def test_game_state_transitions_from_active_to_finished(client):
    """Game.state transitions from active to finished correctly"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        
        assert game.state == "active"
    
    # End game via resignation
    client.post("/resign", 
                data='{"color": "white"}', 
                content_type="application/json")
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        
        assert game.state == "finished"


def test_cascade_delete_game_moves(client):
    """Deleting a game cascades to delete GameMoves"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
    
    # Make several moves
    for _ in range(3):
        make_move(client, "e2", "e4")
        make_move(client, "e7", "e5")
    
    # Verify moves exist
    with app.app_context():
        moves_before = GameMove.query.filter_by(game_id=game_id).count()
        assert moves_before > 0
        
        # Delete the game
        game = db.session.get(Game, game_id)
        db.session.delete(game)
        db.session.commit()
        
        # Verify cascaded delete of moves
        moves_after = GameMove.query.filter_by(game_id=game_id).count()
        assert moves_after == 0


def test_game_uuid_uniqueness(client):
    """Each player gets a unique UUID"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        uuid1 = sess.get("player_uuid")
    
    # New client session
    with app.test_client() as client2:
        from helpers import init_game
        with client2.session_transaction() as sess:
            from helpers import init_game
            init_game()
            uuid2 = sess.get("player_uuid")
    
    # UUIDs should be different
    assert uuid1 != uuid2


def test_ai_enabled_flag_persists(client):
    """ai_enabled flag is set and persists in database"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        
        # Default is true
        assert game.ai_enabled == True


def test_game_timestamps_set_on_creation(client):
    """started_at is set when game is created"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        
        assert game.started_at is not None
        assert game.ended_at is None


def test_game_result_null_until_game_over(client):
    """result field is null while game is active"""
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        
        assert game.result is None


def test_game_result_set_on_completion(client):
    """result field is set when game completes"""
    reset_board(client)
    
    # End game
    client.post("/resign", 
                data='{"color": "white"}', 
                content_type="application/json")
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        
        assert game.result is not None
        assert game.result in ["1-0", "0-1", "1/2-1/2"]


def test_move_number_increments(client):
    """GameMove.move_number increments correctly"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    make_move(client, "e2", "e4")
    make_move(client, "e7", "e5")
    make_move(client, "g1", "f3")
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        moves = GameMove.query.filter_by(game_id=game_id).order_by(GameMove.move_number).all()
        
        assert len(moves) == 3
        assert moves[0].move_number == 1
        assert moves[1].move_number == 2
        assert moves[2].move_number == 3


def test_game_move_color_alternates(client):
    """GameMove.color alternates between white and black"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    make_move(client, "e2", "e4")
    make_move(client, "e7", "e5")
    make_move(client, "g1", "f3")
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        moves = GameMove.query.filter_by(game_id=game_id).order_by(GameMove.move_number).all()
        
        assert moves[0].color == "white"
        assert moves[1].color == "black"
        assert moves[2].color == "white"


def test_capture_move_has_capture_flag(client):
    """Capture moves are correctly identified"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Non-capture move
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    
    # Capture move
    rv = make_move(client, "e4", "d5")
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        capture_move = GameMove.query.filter_by(game_id=game_id, move_number=3).first()
        
        # Capture should have 'x' in SAN notation
        assert "x" in capture_move.san


def test_game_with_ai_enabled_logged_correctly(client):
    """ai_enabled flag is true for AI games"""
    app.config['AI_ENABLED'] = True
    reset_board(client)
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        
        assert game.ai_enabled == True


def test_all_result_types_stored(client):
    """All result types (1-0, 0-1, 1/2-1/2) are stored correctly"""
    # Test 1-0 (white wins)
    reset_board(client)
    client.post("/resign", 
                data='{"color": "black"}', 
                content_type="application/json")
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        assert game.result == "1-0"
    
    # Test 0-1 (black wins)
    reset_board(client)
    client.post("/resign", 
                data='{"color": "white"}', 
                content_type="application/json")
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        assert game.result == "0-1"
    
    # Test 1/2-1/2 (draw)
    reset_board(client)
    with client.session_transaction() as sess:
        sess['fen'] = '8/8/8/4k3/8/8/4K2N/8 w - - 100 50'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    client.post("/claim-draw/50-move")
    
    with client.session_transaction() as sess:
        game_id = sess.get("game_id")
        game = db.session.get(Game, game_id)
        assert game.result == "1/2-1/2"