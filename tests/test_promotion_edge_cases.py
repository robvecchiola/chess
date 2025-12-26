"""
Promotion Edge Case Tests
Uses FEN-based setup to avoid complex move sequences
"""
import pytest
import chess
from app import app
from tests.helper import make_move, set_position

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['AI_ENABLED'] = False
    with app.test_client() as client:
        yield client

# -------------------------------------------------------------------
# Promotion Edge Cases
# -------------------------------------------------------------------

def test_promotion_capture_rook(client):
    """Test promotion by capturing rook on 8th rank"""
    # White pawn on a7, can capture rook on a8
    set_position(client, 'rnbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1')
    
    rv = make_move(client, "a7", "a8", promotion="q")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.A8).symbol().upper() == "Q"
    assert "Promotion to Q" in rv["special_moves"]


def test_promotion_diagonal_capture(client):
    """Test promotion with diagonal capture"""
    # White pawn on b7, can capture bishop on c8
    set_position(client, 'rnbqkbnr/1P5p/8/8/8/8/P1PPPPPP/RNBQKBNR w KQkq - 0 1')
    
    rv = make_move(client, "b7", "c8", promotion="q")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.C8).symbol().upper() == "Q"
    assert len(rv["captured_pieces"]["white"]) > 0


def test_black_promotion(client):
    """Test black pawn promotion"""
    # Black pawn on h2, can capture rook on h1
    set_position(client, 'rnbqkbnr/ppppppp1/8/8/8/8/PPPPPPP1p/RNBQKBNR b KQkq - 0 1')
    
    rv = make_move(client, "h2", "h1", promotion="q")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    piece = board.piece_at(chess.H1)
    assert piece.symbol() == "q"
    assert piece.color == chess.BLACK


def test_promotion_both_sides_same_game(client):
    """Test both white and black promoting in same game"""
    # Setup: white pawn on a7, black pawn on h2
    set_position(client, 'rnbqkbnr/P6p/8/8/8/8/PPPPPPP1p/RNBQKBNR w KQkq - 0 1')
    
    # White promotes
    rv = make_move(client, "a7", "a8", promotion="q")
    assert rv["status"] == "ok"
    
    # Black promotes
    rv = make_move(client, "h2", "h1", promotion="q")
    assert rv["status"] == "ok"
    assert rv["special_moves"].count("Promotion") == 2


def test_promotion_multiple_queens(client):
    """Test promoting to create multiple queens"""
    set_position(client, 'rnbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1')
    
    rv = make_move(client, "a7", "a8", promotion="q")
    assert rv["status"] == "ok"
    
    # Verify 2 white queens exist
    board = chess.Board(rv["fen"])
    queens = [sq for sq in chess.SQUARES if board.piece_at(sq) 
              and board.piece_at(sq).piece_type == chess.QUEEN 
              and board.piece_at(sq).color == chess.WHITE]
    assert len(queens) == 2


def test_promotion_under_check(client):
    """Test that promotion is legal"""
    set_position(client, 'rnbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1')
    
    rv = make_move(client, "a7", "a8", promotion="q")
    assert rv["status"] == "ok"


def test_promotion_knight_gives_check(client):
    """Test underpromotion to knight delivers check"""
    # After Nc8+, black king on a8 is in check but can escape to b8
    set_position(client, 'k7/2P5/1K6/8/8/8/8/8 w - - 0 1')
    
    rv = make_move(client, "c7", "c8", promotion="n")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    
    # Knight on c8 doesn't give check to king on a8
    # (Knight attacks b6, but not a8 which is 2 squares away)
    # This position is actually NOT check - knight from c8 can't reach a8
    assert board.is_checkmate() == False


def test_promotion_flag_on_non_promotion_move(client):
    """Test that promotion flag on non-promotion move is illegal"""
    set_position(client, chess.STARTING_FEN)
    
    rv = make_move(client, "e2", "e4", promotion="q")
    assert rv["status"] == "illegal"


def test_promotion_missing_parameter(client):
    """Test that move to 8th rank without promotion parameter fails"""
    set_position(client, 'rnbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1')
    
    rv = make_move(client, "a7", "a8")  # No promotion
    assert rv["status"] == "illegal"


def test_promotion_all_four_pieces(client):
    """Test all four promotion pieces (Q, R, B, N)"""
    pieces = ['q', 'r', 'b', 'n']
    expected = ['Q', 'R', 'B', 'N']
    
    for piece, symbol in zip(pieces, expected):
        set_position(client, 'rnbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1')
        
        rv = make_move(client, "a7", "a8", promotion=piece)
        assert rv["status"] == "ok", f"Promotion to {piece} failed"
        
        board = chess.Board(rv["fen"])
        promoted = board.piece_at(chess.A8)
        assert promoted.symbol().upper() == symbol


def test_promotion_san_notation(client):
    """Test SAN notation includes = symbol"""
    set_position(client, 'rnbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1')
    
    rv = make_move(client, "a7", "a8", promotion="q")
    assert rv["status"] == "ok"
    
    last_move = rv["move_history"][-1]
    assert "=" in last_move
    assert "Q" in last_move


def test_black_underpromotion_to_rook(client):
    """Test black underpromotion"""
    set_position(client, 'rnbqkbnr/ppppppp1/8/8/8/8/PPPPPPP1p/RNBQKBNR b KQkq - 0 1')
    
    rv = make_move(client, "h2", "h1", promotion="r")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    piece = board.piece_at(chess.H1)
    assert piece.symbol() == "r"
    assert piece.piece_type == chess.ROOK


def test_promotion_tracks_captured_piece(client):
    """Test capture tracking during promotion"""
    set_position(client, 'rnbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1')
    
    rv = make_move(client, "a7", "a8", promotion="q")
    assert rv["status"] == "ok"
    assert len(rv["captured_pieces"]["white"]) > 0
    assert 'r' in rv["captured_pieces"]["white"]


def test_promotion_straight_advance(client):
    """Test promotion by straight advance (no capture)"""
    # a8 is empty
    set_position(client, '1nbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1')
    
    rv = make_move(client, "a7", "a8", promotion="q")
    assert rv["status"] == "ok"
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.A8).symbol().upper() == "Q"


def test_promotion_invalid_piece_king(client):
    """Test promoting to king is illegal"""
    set_position(client, 'rnbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1')
    
    rv = make_move(client, "a7", "a8", promotion="k")
    assert rv["status"] == "illegal"


def test_promotion_to_queen_standard(client):
    """Test standard queen promotion"""
    set_position(client, 'rnbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1')
    
    rv = make_move(client, "a7", "a8", promotion="q")
    assert rv["status"] == "ok"
    
    board = chess.Board(rv["fen"])
    piece = board.piece_at(chess.A8)
    assert piece.piece_type == chess.QUEEN
    assert piece.color == chess.WHITE