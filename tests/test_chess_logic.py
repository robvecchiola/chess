import chess
import pytest

@pytest.fixture
def new_board():
    """Return a fresh chess board."""
    return chess.Board()

def test_initial_position(new_board):
    assert new_board.fen().startswith("rnbqkbnr")

def test_legal_pawn_move(new_board):
    move = chess.Move.from_uci("e2e4")
    assert move in new_board.legal_moves
    new_board.push(move)
    assert new_board.piece_at(chess.E4).symbol() == "P"

def test_illegal_pawn_move(new_board):
    move = chess.Move.from_uci("e2e5")
    assert move not in new_board.legal_moves

def test_capture(new_board):
    new_board.set_fen("8/8/8/3p4/4P3/8/8/8 w - - 0 1")
    move = chess.Move.from_uci("e4d5")
    assert move in new_board.legal_moves
    new_board.push(move)
    assert new_board.piece_at(chess.D5).symbol() == "P"

def test_promotion(new_board):
    new_board.set_fen("8/P7/8/8/8/8/8/8 w - - 0 1")
    move = chess.Move.from_uci("a7a8q")
    assert move in new_board.legal_moves
    new_board.push(move)
    assert new_board.piece_at(chess.A8).symbol().lower() == "q"

def test_en_passant(new_board):
    new_board.set_fen("8/8/8/1pP5/8/8/8/8 w - b6 0 1")
    move = chess.Move.from_uci("c5b6")
    assert move in new_board.legal_moves
    new_board.push(move)
    assert new_board.piece_at(chess.B6).symbol() == "P"

def test_knight_moves(new_board):
    # Place knight on d4
    new_board.set_fen("8/8/8/8/3N4/8/8/8 w - - 0 1")
    # Test some knight moves
    moves = ["d4c2", "d4e2", "d4b3", "d4f3", "d4b5", "d4f5", "d4c6", "d4e6"]
    for uci in moves:
        move = chess.Move.from_uci(uci)
        assert move in new_board.legal_moves

def test_bishop_moves(new_board):
    # Place bishop on d4
    new_board.set_fen("8/8/8/8/3B4/8/8/8 w - - 0 1")
    # Test diagonal moves
    moves = ["d4c3", "d4e3", "d4c5", "d4e5", "d4b2", "d4f2", "d4b6", "d4f6", "d4a1", "d4g1", "d4a7", "d4g7", "d4h8"]
    for uci in moves:
        move = chess.Move.from_uci(uci)
        assert move in new_board.legal_moves

def test_rook_moves(new_board):
    # Place rook on d4
    new_board.set_fen("8/8/8/8/3R4/8/8/8 w - - 0 1")
    # Test horizontal/vertical moves
    moves = ["d4d1", "d4d2", "d4d3", "d4d5", "d4d6", "d4d7", "d4d8", "d4a4", "d4b4", "d4c4", "d4e4", "d4f4", "d4g4", "d4h4"]
    for uci in moves:
        move = chess.Move.from_uci(uci)
        assert move in new_board.legal_moves

def test_queen_moves(new_board):
    # Place queen on d4
    new_board.set_fen("8/8/8/8/3Q4/8/8/8 w - - 0 1")
    # Test combined rook/bishop moves
    moves = ["d4d1", "d4d8", "d4a4", "d4h4", "d4c3", "d4e5", "d4c5", "d4e3", "d4b6", "d4f6", "d4b2", "d4f2", "d4a7", "d4g7", "d4a1", "d4g1", "d4h8"]
    for uci in moves:
        move = chess.Move.from_uci(uci)
        assert move in new_board.legal_moves

def test_king_moves(new_board):
    # Place king on d4
    new_board.set_fen("8/8/8/8/3K4/8/8/8 w - - 0 1")
    # Test one-square moves
    moves = ["d4c3", "d4c4", "d4c5", "d4d3", "d4d5", "d4e3", "d4e4", "d4e5"]
    for uci in moves:
        move = chess.Move.from_uci(uci)
        assert move in new_board.legal_moves

def test_pinned_piece_cannot_move(new_board):
    # Bishop on d4 is pinned by rook on d8, king on d1
    new_board.set_fen("3r4/8/8/8/3B4/8/8/3K4 w - - 0 1")
    # The bishop is absolutely pinned - any move exposes the king
    # Only the king can move in this position
    illegal_moves = ["d4c3", "d4e3", "d4c5", "d4e5", "d4d2", "d4d3", "d4d5", "d4d6", "d4d7", "d4d8"]
    for uci in illegal_moves:
        move = chess.Move.from_uci(uci)
        assert move not in new_board.legal_moves
    # Only king moves are legal
    king_moves = ["d1e2", "d1d2", "d1c2", "d1e1", "d1c1"]
    for uci in king_moves:
        move = chess.Move.from_uci(uci)
        assert move in new_board.legal_moves

def test_discovery_check(new_board):
    # White rook on a1, black king on a8, white bishop on a4
    # Moving bishop reveals check from rook
    new_board.set_fen("k7/8/8/8/B7/8/8/R6K w - - 0 1")
    move = chess.Move.from_uci("a4b5")  # Bishop moves, revealing check
    new_board.push(move)
    assert new_board.is_check() == True
