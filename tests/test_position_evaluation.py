"""
Unit and Integration Tests for Position Evaluation System

Tests the evaluate_board() function which combines:
1. Material scoring (piece values)
2. Piece-square table bonuses (positional evaluation)
3. Game-over detection (checkmate, stalemate)
"""
import chess
import pytest
from ai import evaluate_board, quiescence, minimax
from constants import PIECE_VALUES


# =============================================================================
# UNIT TESTS - evaluate_board() Function
# =============================================================================

@pytest.mark.unit
def test_evaluation_starting_position_near_zero():
    """Starting position should be roughly equal"""
    board = chess.Board()
    score = evaluate_board(board)
    
    # Starting position should be close to 0 (slight white advantage due to tempo)
    assert abs(score) < 100, f"Starting position should be near 0, got {score}"


@pytest.mark.unit
def test_evaluation_white_material_advantage():
    """White up a queen should have positive evaluation"""
    board = chess.Board()
    board.remove_piece_at(chess.D8)  # Remove black queen
    
    score = evaluate_board(board)
    
    # Should be positive (white advantage)
    assert score > 0, f"White up queen should have positive eval, got {score}"
    # Should be at least queen value (accounting for piece-square table penalties/bonuses)
    assert score >= PIECE_VALUES[chess.QUEEN] - 50, f"Score should be close to queen value (900±50), got {score}"


@pytest.mark.unit
def test_evaluation_black_material_advantage():
    """Black up a queen should have negative evaluation"""
    board = chess.Board()
    board.remove_piece_at(chess.D1)  # Remove white queen
    
    score = evaluate_board(board)
    
    # Should be negative (black advantage)
    assert score < 0, f"Black up queen should have negative eval, got {score}"
    assert score <= -PIECE_VALUES[chess.QUEEN] + 50, f"Score should be close to -queen value (-900±50), got {score}"


@pytest.mark.unit
def test_evaluation_checkmate_white_wins():
    """Checkmate for white should return maximum positive score"""
    # Fool's mate position - white checkmated
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2")
    board.push(chess.Move.from_uci("d8h4"))  # Checkmate
    
    assert board.is_checkmate()
    
    score = evaluate_board(board)
    
    # Black checkmated white → very negative score
    assert score < -50000, f"Checkmate should be extreme negative, got {score}"


@pytest.mark.unit
def test_evaluation_checkmate_black_loses():
    """Checkmate for black should return maximum negative score"""
    # Back rank mate
    board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/R6K b - - 0 1")
    
    # Move king into corner
    board.push(chess.Move.from_uci("g8h8"))
    # Deliver checkmate
    board.push(chess.Move.from_uci("a1a8"))
    
    assert board.is_checkmate()
    
    score = evaluate_board(board)
    
    # White checkmated black → very positive score
    assert score > 50000, f"Checkmate should be extreme positive, got {score}"


@pytest.mark.unit
def test_evaluation_stalemate_is_zero():
    """Stalemate should return 0 (draw)"""
    # Stalemate position
    board = chess.Board("7k/8/6Q1/8/8/8/8/K7 b - - 0 1")
    
    assert board.is_stalemate()
    
    score = evaluate_board(board)
    assert score == 0, f"Stalemate should be 0, got {score}"


@pytest.mark.unit
def test_evaluation_insufficient_material_is_zero():
    """Insufficient material draw should return 0"""
    # King vs King
    board = chess.Board("8/8/8/8/8/8/8/K6k w - - 0 1")
    
    assert board.is_insufficient_material()
    
    score = evaluate_board(board)
    assert score == 0, f"Insufficient material should be 0, got {score}"


@pytest.mark.unit
def test_evaluation_includes_piece_square_tables():
    """Evaluation should include positional bonuses from piece-square tables"""
    # Create two positions with same material but different piece positions
    
    # Position 1: Pawn on a2 (starting square) - has piece-square bonus of 50
    board1 = chess.Board("8/8/8/8/8/8/P7/K6k w - - 0 1")
    score1 = evaluate_board(board1)
    
    # Position 2: Pawn on e4 (center, advanced) - has piece-square bonus of 20
    board2 = chess.Board("8/8/8/8/4P3/8/8/K6k w - - 0 1")
    score2 = evaluate_board(board2)
    
    # Both have same material (1 pawn = 100), scores differ by piece-square table
    # Verify evaluation includes positional component (not just material)
    assert score1 != score2, \
        f"Different pawn positions should have different scores: e4({score2}) vs a2({score1})"


@pytest.mark.unit
def test_evaluation_knight_center_vs_edge():
    """Knights should be valued higher in center than on edge"""
    # Test using starting position + modifications to see piece-square effect
    
    # Position 1: White knight on a1 (bad square)
    board1 = chess.Board()
    board1.remove_piece_at(chess.B1)  # Remove b1 knight
    board1.set_piece_at(chess.A1, chess.Piece(chess.KNIGHT, chess.WHITE))  # Knight to a1
    score1 = evaluate_board(board1)
    
    # Position 2: White knight on d4 (good square)
    board2 = chess.Board()
    board2.remove_piece_at(chess.B1)  # Remove b1 knight
    board2.set_piece_at(chess.D4, chess.Piece(chess.KNIGHT, chess.WHITE))  # Knight to d4
    score2 = evaluate_board(board2)
    
    # Center knight should score higher
    assert score2 > score1, \
        f"Center knight should score higher: d4({score2}) vs a1({score1})"


@pytest.mark.unit
def test_evaluation_symmetry():
    """Evaluation should be symmetric for white/black pieces"""
    # White knight on e4
    board_white = chess.Board("8/8/8/8/4N3/8/8/K6k w - - 0 1")
    score_white = evaluate_board(board_white)
    
    # Black knight on e5 (mirrored position)
    board_black = chess.Board("K6k/8/8/4n3/8/8/8/8 b - - 0 1")
    score_black = evaluate_board(board_black)
    
    # Should be roughly opposite (within rounding)
    assert abs(score_white + score_black) < 50, \
        f"Scores should be symmetric: white={score_white}, black={score_black}"


@pytest.mark.unit
def test_evaluation_promotion_improves_score():
    """Promoting pawn to queen should improve evaluation"""
    # White pawn on a7, ready to promote
    board = chess.Board("1nbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1")
    
    score_before = evaluate_board(board)
    
    # Promote to queen
    board.push(chess.Move.from_uci("a7a8q"))
    
    score_after = evaluate_board(board)
    
    # Promotion should significantly improve white's position
    # Gain = queen value (900) - pawn value (100) + positional bonus
    assert score_after > score_before + 700, \
        f"Promotion should improve score: before={score_before}, after={score_after}"


@pytest.mark.unit
def test_evaluation_capture_improves_score():
    """Capturing opponent's piece should improve evaluation"""
    # Position where white can capture black queen
    board = chess.Board("rnb1kbnr/pppppppp/8/8/8/2N5/PPPPPPPP/R1BQKBNR w KQkq - 0 1")
    
    # Put black queen where knight can capture it
    board.set_piece_at(chess.E4, chess.Piece(chess.QUEEN, chess.BLACK))
    
    score_before = evaluate_board(board)
    
    # Capture queen
    board.push(chess.Move.from_uci("c3e4"))
    
    score_after = evaluate_board(board)
    
    # Capturing queen should significantly improve white's score
    assert score_after > score_before + 700, \
        f"Capturing queen should improve score: before={score_before}, after={score_after}"


@pytest.mark.unit
def test_evaluation_king_safety_endgame():
    """Evaluation correctly applies king piece-square values"""
    # Use starting position with king in different locations
    
    # Endgame position: king + pawn vs king
    # White king on e1 (edge) vs e4 (center)
    board1 = chess.Board("8/8/8/8/4p3/8/8/4K2k w - - 0 1")
    score1 = evaluate_board(board1)
    
    # Same position but white king on e4 (centralized)
    board2 = chess.Board("8/8/8/8/4K3/8/4p3/7k w - - 0 1")
    score2 = evaluate_board(board2)
    
    # Centralized king should be better in endgame
    assert score2 > score1, \
        f"Centralized king (e4) should score higher than edge king (e1): e1={score1} vs e4={score2}"


# =============================================================================
# UNIT TESTS - Quiescence Search
# =============================================================================

@pytest.mark.unit
def test_quiescence_captures_and_checks():
    """Quiescence should explore captures and checks"""
    # Position with hanging queen
    board = chess.Board("r6k/8/8/8/8/2N5/PPPPPPPP/R1BQKBNR w KQkq - 0 1")
    board.set_piece_at(chess.E4, chess.Piece(chess.QUEEN, chess.BLACK))
    
    # Quiescence should find the queen capture
    score = quiescence(board, -float('inf'), float('inf'))
    
    # Should recognize the queen capture opportunity
    assert score > 0, f"Quiescence should find positive evaluation, got {score}"


@pytest.mark.unit
def test_quiescence_depth_limit():
    """Quiescence should not exceed max depth"""
    board = chess.Board()
    
    # Should complete without stack overflow
    score = quiescence(board, -float('inf'), float('inf'), depth=0, max_depth=4)
    
    # Should return some score (not crash)
    assert isinstance(score, (int, float)), "Quiescence should return numeric score"


@pytest.mark.unit
def test_quiescence_beta_cutoff():
    """Quiescence should perform beta cutoffs"""
    board = chess.Board()
    
    # Set tight bounds
    alpha = -100
    beta = 100
    
    score = quiescence(board, alpha, beta)
    
    # Score should be within bounds or at cutoff
    assert score <= beta, f"Score should not exceed beta: {score} <= {beta}"


# =============================================================================
# UNIT TESTS - Minimax Algorithm
# =============================================================================

@pytest.mark.unit
def test_minimax_finds_checkmate_in_one():
    """Minimax should find checkmate when available"""
    # Back rank mate available
    board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1")
    
    # Minimax should find Ra8#
    score = minimax(board, 2, -float('inf'), float('inf'), True)
    
    # Should recognize this is winning
    assert score > 50000, f"Should find checkmate, got score {score}"


@pytest.mark.unit
def test_minimax_white_maximizes():
    """Minimax should maximize for white"""
    board = chess.Board()
    
    # White's turn (maximizing)
    score = minimax(board, 2, -float('inf'), float('inf'), True)
    
    # Should return some evaluation
    assert isinstance(score, (int, float)), "Minimax should return numeric score"


@pytest.mark.unit
def test_minimax_black_minimizes():
    """Minimax should minimize for black"""
    board = chess.Board()
    board.push(chess.Move.from_uci("e2e4"))  # Make it black's turn
    
    # Black's turn (minimizing)
    score = minimax(board, 2, -float('inf'), float('inf'), False)
    
    # Should return some evaluation
    assert isinstance(score, (int, float)), "Minimax should return numeric score"


@pytest.mark.unit
def test_minimax_alpha_beta_pruning():
    """Minimax should use alpha-beta pruning efficiently"""
    board = chess.Board()
    
    # Should complete quickly with pruning
    import time
    start = time.time()
    score = minimax(board, 3, -float('inf'), float('inf'), True)
    duration = time.time() - start
    
    # Depth 3 should complete in reasonable time
    assert duration < 10.0, f"Minimax took too long: {duration}s"


@pytest.mark.unit
def test_minimax_depth_zero_calls_quiescence():
    """At depth 0, minimax should call quiescence"""
    board = chess.Board()
    
    # Depth 0 should use quiescence
    score_minimax = minimax(board, 0, -float('inf'), float('inf'), True)
    score_quiescence = quiescence(board, -float('inf'), float('inf'))
    
    # Should return similar scores (both use quiescence)
    assert abs(score_minimax - score_quiescence) < 100, \
        f"Depth 0 minimax should match quiescence: {score_minimax} vs {score_quiescence}"


# =============================================================================
# UNIT TESTS - Edge Cases
# =============================================================================

@pytest.mark.unit
def test_evaluation_multiple_queens():
    """Position with multiple queens (from promotion) evaluates correctly"""
    # White has 3 queens, black has 1
    board = chess.Board("Q1Q4k/8/8/8/8/8/8/Q6K w - - 0 1")
    
    score = evaluate_board(board)
    
    # White has huge material advantage
    assert score > 2000, f"Multiple queens should give huge advantage, got {score}"


@pytest.mark.unit
def test_evaluation_minimal_pieces():
    """Evaluation works with very few pieces on board"""
    # Just kings and one pawn
    board = chess.Board("8/8/8/8/8/8/P7/K6k w - - 0 1")
    
    score = evaluate_board(board)
    
    # Should still evaluate correctly
    assert score > 0, f"White pawn advantage should be positive, got {score}"


@pytest.mark.unit
def test_evaluation_asymmetric_armies():
    """Different army compositions evaluate correctly"""
    # White: 3 knights, Black: 2 rooks
    board = chess.Board("r1r5/8/8/8/8/8/8/N1N1N2K w - - 0 1")
    
    score = evaluate_board(board)
    
    # 2 rooks (1000) slightly better than 3 knights (960)
    # But positional factors matter
    assert isinstance(score, (int, float)), "Should evaluate mixed armies"


@pytest.mark.unit
def test_evaluation_en_passant_position():
    """Evaluation handles en passant positions correctly"""
    board = chess.Board("rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 1")
    
    score = evaluate_board(board)
    
    # Should not crash on en passant squares
    assert isinstance(score, (int, float)), "Should handle en passant positions"


@pytest.mark.unit
def test_evaluation_all_piece_types():
    """Evaluation correctly handles all piece types"""
    board = chess.Board()  # Starting position has all piece types
    
    score = evaluate_board(board)
    
    # Verify all pieces contribute to evaluation
    # Starting position should be close to even
    assert abs(score) < 100, f"Starting position should be balanced, got {score}"


# =============================================================================
# INTEGRATION TESTS - Evaluation in API Responses
# =============================================================================

@pytest.mark.integration
def test_move_response_includes_evaluation(client):
    """API response should include evaluation score"""
    from tests.test_routes_api import make_move, reset_board
    from app import create_app
    from config import TestingConfig
    
    app = create_app(TestingConfig)

    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    rv = make_move(client, "e2", "e4")
    
    assert rv["status"] == "ok"
    assert "evaluation" in rv, "Response should include evaluation"
    assert isinstance(rv["evaluation"], (int, float)), "Evaluation should be numeric"


@pytest.mark.integration
def test_evaluation_changes_after_capture(client):
    """Evaluation should improve after capturing opponent's piece"""
    from tests.test_routes_api import make_move, reset_board
    from app import create_app
    from config import TestingConfig
    
    app = create_app(TestingConfig)
    
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up capture
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    
    rv = make_move(client, "e4", "d5")  # White captures
    
    assert rv["status"] == "ok"
    assert "evaluation" in rv
    # White should have advantage after capturing
    assert rv["evaluation"] > 0, f"White should have advantage after capture, got {rv['evaluation']}"


@pytest.mark.integration
def test_evaluation_in_checkmate_position(client):
    """Evaluation should be extreme for checkmate"""
    from tests.test_routes_api import make_move, reset_board
    from app import create_app
    from config import TestingConfig
    
    app = create_app(TestingConfig)
    
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Fool's mate
    moves = [("f2","f3"), ("e7","e5"), ("g2","g4"), ("d8","h4")]
    for from_sq, to_sq in moves:
        rv = make_move(client, from_sq, to_sq)
    
    assert rv["checkmate"] == True
    assert "evaluation" in rv
    # Black checkmated white → extreme negative
    assert rv["evaluation"] < -50000, \
        f"Checkmate should have extreme evaluation, got {rv['evaluation']}"


@pytest.mark.integration
def test_material_and_evaluation_both_present(client):
    """Both material and evaluation should be in response"""
    from tests.test_routes_api import make_move, reset_board
    from app import create_app
    from config import TestingConfig
    
    app = create_app(TestingConfig)
    
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    rv = make_move(client, "e2", "e4")
    
    assert "material" in rv, "Response should include material"
    assert "evaluation" in rv, "Response should include evaluation"
    
    # They should be different (evaluation includes positional factors)
    # After e4, evaluation should be slightly better than just material
    assert isinstance(rv["material"], (int, float))
    assert isinstance(rv["evaluation"], (int, float))


@pytest.mark.integration
def test_reset_clears_evaluation(client):
    """Reset should return evaluation to starting value"""
    from tests.test_routes_api import make_move, reset_board
    from app import create_app
    from config import TestingConfig
    
    app = create_app(TestingConfig)
    
    app.config['AI_ENABLED'] = False
    
    # Make some moves
    reset_board(client)
    make_move(client, "e2", "e4")
    make_move(client, "d7", "d5")
    make_move(client, "e4", "d5")
    
    # Reset
    reset_board(client)
    rv = make_move(client, "e2", "e4")
    
    # Evaluation should be from starting position (not accumulated)
    assert "evaluation" in rv
    assert abs(rv["evaluation"]) < 100, \
        f"After reset, evaluation should be near 0, got {rv['evaluation']}"


# =============================================================================
# FIXTURE
# =============================================================================

@pytest.fixture
def client():
    """Flask test client for integration tests"""
    from app import create_app
    from config import TestingConfig
    
    app = create_app(TestingConfig)
    
    app.config['TESTING'] = True
    app.config['AI_ENABLED'] = False
    
    with app.test_client() as client:
        yield client
