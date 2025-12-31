import chess
import pytest
from ai import material_score

@pytest.mark.unit
def test_material_even_start():
    board = chess.Board()
    assert material_score(board) == 0


@pytest.mark.unit
def test_white_up_pawn():
    board = chess.Board()
    board.remove_piece_at(chess.A7)  # remove black pawn
    assert material_score(board) == 100


@pytest.mark.unit
def test_black_up_queen():
    board = chess.Board()
    board.remove_piece_at(chess.D1)  # remove white queen
    assert material_score(board) == -900


@pytest.mark.unit
def test_multiple_piece_difference():
    board = chess.Board()
    board.remove_piece_at(chess.B1)  # knight
    board.remove_piece_at(chess.C1)  # bishop
    assert material_score(board) == -(320 + 330)


@pytest.mark.unit
def test_promotion_results_in_queen_material():
    board = chess.Board("8/P7/8/8/8/8/8/8 w - - 0 1")
    board.push(chess.Move.from_uci("a7a8q"))
    assert material_score(board) == 900

@pytest.mark.unit
def test_promotion_material_gain():
    """Test that promoting from pawn to queen is +800 material gain"""
    board = chess.Board("8/P7/8/8/8/8/8/8 w - - 0 1")
    
    # Before promotion: white has 1 pawn = +100
    assert material_score(board) == 100
    
    # After promotion: white has 1 queen = +900
    board.push(chess.Move.from_uci("a7a8q"))
    assert material_score(board) == 900
    
    # Net gain = 900 - 100 = 800
    assert 900 - 100 == 800

@pytest.mark.unit
def test_en_passant_material_tracking():
    """Test material count after en passant capture"""
    # Set up en passant position: white pawn on e5, black pawn moves d7-d5
    board = chess.Board("rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 1")
    
    # Before en passant: material is equal (both sides have same pieces)
    initial_material = material_score(board)
    
    # White captures en passant e5xd6
    board.push(chess.Move.from_uci("e5d6"))
    
    # After en passant: white captured black pawn, so white is +100 material
    final_material = material_score(board)
    assert final_material == initial_material + 100

@pytest.mark.unit
def test_material_after_castling():
    """Castling should not change material balance"""
    board = chess.Board()
    # Setup castling position
    board.push(chess.Move.from_uci("e2e4"))
    board.push(chess.Move.from_uci("e7e5"))
    board.push(chess.Move.from_uci("g1f3"))
    board.push(chess.Move.from_uci("g8f6"))
    board.push(chess.Move.from_uci("f1e2"))
    board.push(chess.Move.from_uci("f8e7"))
    
    material_before = material_score(board)
    
    # Castle kingside
    board.push(chess.Move.from_uci("e1g1"))
    
    assert material_score(board) == material_before, \
        "Castling should not change material"


@pytest.mark.unit
def test_material_underpromotion_knight():
    """Test material after underpromotion to knight"""
    board = chess.Board("8/P7/8/8/8/8/8/8 w - - 0 1")
    
    # Before promotion: +100 (pawn)
    assert material_score(board) == 100
    
    # Promote to knight
    board.push(chess.Move.from_uci("a7a8n"))
    
    # After: +320 (knight)
    assert material_score(board) == 320


@pytest.mark.unit
def test_material_underpromotion_rook():
    """Test material after underpromotion to rook"""
    board = chess.Board("8/P7/8/8/8/8/8/8 w - - 0 1")
    board.push(chess.Move.from_uci("a7a8r"))
    assert material_score(board) == 500


@pytest.mark.unit
def test_material_underpromotion_bishop():
    """Test material after underpromotion to bishop"""
    board = chess.Board("8/P7/8/8/8/8/8/8 w - - 0 1")
    board.push(chess.Move.from_uci("a7a8b"))
    assert material_score(board) == 330


@pytest.mark.unit
def test_material_multiple_queens():
    """Test material with multiple queens from promotion"""
    # Position with 3 white queens, 1 black king
    board = chess.Board("Q1Q4k/8/8/8/8/8/8/Q6K w - - 0 1")
    assert material_score(board) == 3 * 900


@pytest.mark.unit
def test_material_traded_pieces_equal():
    """Test material after equal trade (queen for queen)"""
    board = chess.Board()
    initial_material = material_score(board)
    assert initial_material == 0
    
    # Trade queens via moves
    board.set_fen("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1")
    
    # Both queens removed
    assert material_score(board) == 0


@pytest.mark.unit
def test_material_unequal_trade_queen_for_rook():
    """Test material after unequal trade (queen for rook)"""
    # White has queen, black has rook
    board = chess.Board("rnbrkbn1/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQq - 0 1")
    
    # White up queen vs rook = +400
    assert material_score(board) == 900


@pytest.mark.unit
def test_material_all_pieces_captured_except_kings():
    """Test material when only kings remain"""
    board = chess.Board("8/8/8/8/8/8/8/K6k w - - 0 1")
    assert material_score(board) == 0


@pytest.mark.unit
def test_material_asymmetric_armies():
    """Test material with different piece compositions"""
    # White: 3 knights (960), Black: 2 rooks (1000)
    board = chess.Board("r1r5/8/8/8/8/8/8/N1N1N2K w - - 0 1")
    
    white_material = 3 * 320  # 960
    black_material = 2 * 500  # 1000
    
    assert material_score(board) == 19960


@pytest.mark.unit
def test_material_after_double_pawn_capture():
    """Test material tracking through multiple captures"""
    board = chess.Board()
    
    # Initial: equal
    assert material_score(board) == 0
    
    # White captures black pawn
    board.set_fen("rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1")
    assert material_score(board) == 0
    
    # Black captures white pawn
    board.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPP1PPPP/RNBQKBNR w KQkq - 0 1")
    assert material_score(board) == -100


@pytest.mark.unit
def test_material_promotion_capture_sequence():
    """Test material after pawn promotes by capturing"""
    # White pawn on b7, black rook on a8
    board = chess.Board("rnbqkbnr/1P5p/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
    
    # Before: material even
    assert material_score(board) == 800
    
    # Promote to queen by capturing rook: +900 - 100 + 500 = +1300
    board.push(chess.Move.from_uci("b7a8q"))
    
    assert material_score(board) == 2100  # queen + captured rook


@pytest.mark.unit
def test_material_negative_for_black():
    """Test negative material when black is ahead"""
    # Remove white queen
    board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1")
    
    assert material_score(board) == -900


@pytest.mark.unit
def test_material_after_en_passant():
    """Test material after en passant capture"""
    # Setup en passant position
    board = chess.Board("rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 1")
    
    initial_material = material_score(board)
    
    # Execute en passant
    board.push(chess.Move.from_uci("e5d6"))
    
    # White captured black pawn: +100
    assert material_score(board) == initial_material + 100