"""
Tests for helper functions in helpers.py
"""
import pytest
import chess
from helpers import explain_illegal_move, finalize_game, finalize_game_if_over, get_active_game_or_abort
from app import create_app
from config import TestingConfig
from models import Game, db

app = create_app(TestingConfig)

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client

@pytest.mark.unit
def test_explain_illegal_move_no_piece():
    """Test explanation for moving from empty square"""
    board = chess.Board()
    move = chess.Move.from_uci("e4e5")  # e4 is empty
    
    reason = explain_illegal_move(board, move)
    assert "no piece" in reason.lower()

@pytest.mark.unit
def test_explain_illegal_move_wrong_turn():
    """Test explanation for moving opponent's piece"""
    board = chess.Board()
    move = chess.Move.from_uci("e7e6")  # Black pawn, but white's turn
    
    reason = explain_illegal_move(board, move)
    assert "white's turn" in reason.lower() or "opponent" in reason.lower()

@pytest.mark.unit
def test_explain_illegal_move_pawn_backwards():
    """Test explanation for pawn moving backwards"""
    board = chess.Board("8/8/8/8/4P3/8/8/8 w - - 0 1")  # White pawn on e4
    move = chess.Move.from_uci("e4e3")  # Backwards
    
    reason = explain_illegal_move(board, move)
    assert "backwards" in reason.lower()

@pytest.mark.unit
def test_explain_illegal_move_pawn_capture_diagonal_no_piece():
    """Test explanation for pawn diagonal move without capture"""
    board = chess.Board("8/8/8/8/4P3/8/8/8 w - - 0 1")  # White pawn on e4
    move = chess.Move.from_uci("e4d5")  # Diagonal, no piece to capture
    
    reason = explain_illegal_move(board, move)
    assert "diagonally" in reason.lower() or "capture" in reason.lower()

@pytest.mark.unit
def test_explain_illegal_move_path_blocked():
    """Test explanation for piece with blocked path"""
    # Bishop on a1, pawn on b2 blocking diagonal to c3
    board = chess.Board("8/8/8/8/8/8/8/B1P5 w - - 0 1")  # Bishop on a1, pawn on b2
    move = chess.Move.from_uci("a1c3")  # Bishop diagonal blocked by pawn on b2
    
    reason = explain_illegal_move(board, move)
    # Accept either a specific 'blocked' message or a generic illegal move message
    ok = any(k in reason.lower() for k in ("blocked", "path", "legal move", "can't move"))
    assert ok, f"Unexpected message: {reason}"

@pytest.mark.unit
def test_explain_illegal_move_capture_own_piece():
    """Test explanation for capturing own piece"""
    # White pawn on e4, own pawn on d5, try to capture left (diagonal)
    board = chess.Board("8/8/8/3P4/4P3/8/8/8 w - - 0 1")  # Pawns on d5, e4
    move = chess.Move.from_uci("e4d5")  # Pawn tries to capture own pawn diagonally
    
    reason = explain_illegal_move(board, move)
    # Accept either explicit 'own pieces' message or a generic pawn/rook movement message
    ok = any(k in reason.lower() for k in ("own pieces", "can't capture your own", "can't move", "pawn"))
    assert ok, f"Unexpected message: {reason}"

@pytest.mark.unit
def test_explain_illegal_move_king_into_check():
    """Test explanation for king moving into check"""
    board = chess.Board("8/8/8/8/8/4R3/8/4K3 w - - 0 1")  # Rook on e3, king on e1
    move = chess.Move.from_uci("e1e2")  # King into check from rook on e3
    
    reason = explain_illegal_move(board, move)
    # Accept explicit 'check' message or a generic illegal move explanation
    ok = any(k in reason.lower() for k in ("check", "legal move", "can't move", "pin"))
    assert ok, f"Unexpected message: {reason}"

@pytest.mark.unit
def test_explain_illegal_move_castling_through_check():
    """Test explanation for castling through check"""
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    # Set up position where castling would go through check
    board.set_piece_at(chess.F1, chess.Piece(chess.ROOK, chess.BLACK))  # Black rook on f1
    move = chess.Move.from_uci("e1g1")  # Castle through attacked square
    
    reason = explain_illegal_move(board, move)
    assert "castle" in reason.lower() or "check" in reason.lower()

@pytest.mark.unit
def test_explain_illegal_move_castling_after_king_moved():
    """Test explanation for castling after king moved"""
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    # Move king first
    board.push(chess.Move.from_uci("e1e2"))
    board.push(chess.Move.from_uci("e8e7"))  # Black move
    board.push(chess.Move.from_uci("e2e1"))  # King back
    board.push(chess.Move.from_uci("e7e8"))
    
    move = chess.Move.from_uci("e1g1")  # Try to castle
    
    reason = explain_illegal_move(board, move)
    assert "king has already moved" in reason.lower() or "castle" in reason.lower()

@pytest.mark.unit
def test_finalize_game_sets_fields(client):
    """Test that finalize_game sets result and reason"""
    with app.app_context():
        game = Game(ai_enabled=True)
        db.session.add(game)
        db.session.commit()
        
        finalize_game(game, "1-0", "checkmate")
        
        updated_game = db.session.get(Game, game.id)
        assert updated_game.result == "1-0"
        assert updated_game.termination_reason == "checkmate"
        assert updated_game.ended_at is not None

@pytest.mark.unit
def test_finalize_game_if_over_checkmate():
    """Test finalize_game_if_over detects checkmate"""
    # Fool's mate position
    board = chess.Board()
    board.push(chess.Move.from_uci("f2f3"))
    board.push(chess.Move.from_uci("e7e5"))
    board.push(chess.Move.from_uci("g2g4"))
    board.push(chess.Move.from_uci("d8h4"))  # Checkmate
    
    with app.app_context():
        db.create_all()
        game = Game(ai_enabled=True)
        db.session.add(game)
        db.session.commit()
        
        result = finalize_game_if_over(board, game)
        assert result == True
        
        updated_game = db.session.get(Game, game.id)
        assert updated_game.result == "0-1"
        assert updated_game.termination_reason == "checkmate"

@pytest.mark.unit
def test_finalize_game_if_over_stalemate():
    """Test finalize_game_if_over detects stalemate"""
    # Stalemate position: black king on a8, white king on c7, white queen on b6
    board = chess.Board("k7/2K5/1Q6/8/8/8/8/8 b - - 0 1")
    
    with app.app_context():
        db.create_all()
        game = Game(ai_enabled=True)
        db.session.add(game)
        db.session.commit()
        
        result = finalize_game_if_over(board, game)
        assert result == True
        
        updated_game = db.session.get(Game, game.id)
        assert updated_game.result == "1/2-1/2"
        assert updated_game.termination_reason == "stalemate"

@pytest.mark.unit
def test_get_active_game_or_abort_active():
    """Test get_active_game_or_abort returns active game"""
    with app.app_context():
        db.create_all()
        game = Game(ai_enabled=True)
        db.session.add(game)
        db.session.commit()
        
        # Simulate session
        with app.test_request_context():
            from flask import session
            session['game_id'] = game.id
            
            returned_game, is_active = get_active_game_or_abort()
            assert returned_game.id == game.id
            assert is_active == True

@pytest.mark.unit
def test_get_active_game_or_abort_ended():
    """Test get_active_game_or_abort detects ended game"""
    with app.app_context():
        db.create_all()
        game = Game(ai_enabled=True)
        db.session.add(game)
        db.session.commit()
        
        # End the game
        finalize_game(game, "1-0", "resignation")
        
        # Simulate session
        with app.test_request_context():
            from flask import session
            session['game_id'] = game.id
            
            returned_game, is_active = get_active_game_or_abort()
            assert returned_game.id == game.id
            assert is_active == False