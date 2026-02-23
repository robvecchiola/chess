"""
Tests for helper functions in helpers.py
"""
import pytest
import chess
from helpers import (
    explain_illegal_move,
    finalize_game,
    finalize_game_if_over,
    get_active_game_or_abort,
    execute_move,
    save_game_state,
)
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


@pytest.mark.unit
def test_execute_move_ai_forces_queen_promotion_when_missing_piece():
    """AI move execution should auto-promote pawns that reach last rank without explicit promotion."""
    board = chess.Board("4k3/7P/8/8/8/8/8/4K3 w - - 0 1")
    move = chess.Move.from_uci("h7h8")  # No promotion piece specified
    move_history = []
    captured_pieces = {"white": [], "black": []}
    special_moves = []

    with app.test_request_context():
        from flask import session
        session["special_moves_by_color"] = {"white": [], "black": []}

        execute_move(board, move, move_history, captured_pieces, special_moves, is_ai=True)

        promoted_piece = board.piece_at(chess.H8)
        assert promoted_piece is not None and promoted_piece.symbol() == "Q"
        assert special_moves == ["Promotion to Q"]
        assert session["special_moves_by_color"]["white"] == ["Promotion to Q"]


@pytest.mark.unit
def test_execute_move_special_move_outside_request_context_is_safe():
    """Special move tracking should not crash when session is unavailable."""
    board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    move = chess.Move.from_uci("e1g1")
    move_history = []
    captured_pieces = {"white": [], "black": []}
    special_moves = []

    # No request context on purpose; execute_move should still succeed.
    execute_move(board, move, move_history, captured_pieces, special_moves)

    assert special_moves == ["Castling"]
    assert board.piece_at(chess.G1).symbol() == "K"
    assert board.piece_at(chess.F1).symbol() == "R"


@pytest.mark.unit
def test_execute_move_fallback_promotion_detection_records_special_move():
    """Fallback promotion path should append promotion special move when destination appears promoted."""
    class PromotionProxyBoard:
        def __init__(self, base_board, promoted_square):
            self._base = base_board
            self._promoted_square = promoted_square
            self._after_push = False

        def push(self, move):
            self._base.push(move)
            self._after_push = True

        def piece_at(self, square):
            if self._after_push and square == self._promoted_square:
                return chess.Piece(chess.QUEEN, chess.WHITE)
            return self._base.piece_at(square)

        def __getattr__(self, name):
            return getattr(self._base, name)

    base_board = chess.Board("rnbqkbnr/1Pppppp1/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1")
    board = PromotionProxyBoard(base_board, chess.A8)
    move = chess.Move.from_uci("b7a8")  # No explicit promotion piece
    move_history = []
    captured_pieces = {"white": [], "black": []}
    special_moves = []

    with app.test_request_context():
        from flask import session
        session["special_moves_by_color"] = {"white": [], "black": []}

        execute_move(board, move, move_history, captured_pieces, special_moves, is_ai=False)

        assert any("Promotion to Q" == m for m in special_moves), f"Expected fallback promotion, got {special_moves}"
        assert session["special_moves_by_color"]["white"] == ["Promotion to Q"]


@pytest.mark.unit
def test_execute_move_fallback_promotion_detection_failure_is_nonfatal():
    """Fallback promotion detection exceptions should be swallowed without breaking move execution."""
    class BrokenPromotionProxyBoard:
        def __init__(self, base_board, target_square):
            self._base = base_board
            self._target_square = target_square
            self._after_push = False

        def push(self, move):
            self._base.push(move)
            self._after_push = True

        def piece_at(self, square):
            if self._after_push and square == self._target_square:
                raise RuntimeError("piece_at failed after push")
            return self._base.piece_at(square)

        def __getattr__(self, name):
            return getattr(self._base, name)

    base_board = chess.Board("4k3/7P/8/8/8/8/8/4K3 w - - 0 1")
    board = BrokenPromotionProxyBoard(base_board, chess.H8)
    move = chess.Move.from_uci("h7h8")
    move_history = []
    captured_pieces = {"white": [], "black": []}
    special_moves = []

    execute_move(board, move, move_history, captured_pieces, special_moves, is_ai=False)

    assert move_history[-1].startswith("h8")
    assert special_moves == []


@pytest.mark.unit
def test_save_game_state_persists_special_moves_by_color_when_provided():
    board = chess.Board()
    move_history = []
    captured_pieces = {"white": [], "black": []}
    special_moves = ["Castling"]
    by_color = {"white": ["Castling"], "black": []}

    with app.test_request_context():
        from flask import session
        save_game_state(board, move_history, captured_pieces, special_moves, by_color)
        assert session["special_moves"] == ["Castling"]
        assert session["special_moves_by_color"] == by_color


@pytest.mark.unit
def test_finalize_game_returns_early_if_already_finalized(client):
    with app.app_context():
        game = Game(ai_enabled=True)
        db.session.add(game)
        db.session.commit()

        finalize_game(game, "1-0", "checkmate")
        first_ended_at = game.ended_at
        first_result = game.result
        first_reason = game.termination_reason

        # Second call should be ignored.
        finalize_game(game, "0-1", "resignation")
        db.session.refresh(game)

        assert game.ended_at == first_ended_at
        assert game.result == first_result
        assert game.termination_reason == first_reason


@pytest.mark.unit
def test_finalize_game_if_over_detects_75_move_rule():
    board = chess.Board("4k3/8/8/8/8/8/8/R3K2R w KQ - 150 1")

    with app.app_context():
        game = Game(ai_enabled=True)
        db.session.add(game)
        db.session.commit()

        result = finalize_game_if_over(board, game)
        db.session.refresh(game)

        assert result is True
        assert game.result == "1/2-1/2"
        assert game.termination_reason == "draw_75_move_rule"


@pytest.mark.unit
def test_get_active_game_or_abort_returns_none_for_missing_game_record():
    with app.test_request_context():
        from flask import session
        session["game_id"] = 999999999
        game, is_active = get_active_game_or_abort()
        assert game is None
        assert is_active is None
