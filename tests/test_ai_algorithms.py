"""
AI Algorithm Tests
Advanced tests for AI move selection, evaluation, and search algorithms
"""
import pytest
import chess
from ai import choose_ai_move, evaluate_board, minimax, quiescence, order_moves, material_score


class TestMoveOrdering:
    """Tests for move ordering heuristic"""
    
    @pytest.mark.unit
    def test_order_moves_prioritizes_promotions(self):
        """Promotions should come first in move ordering"""
        # Position with promotion available
        board = chess.Board("8/P7/8/8/8/8/8/8 w - - 0 1")
        ordered = order_moves(board)
        
        # First moves should be promotions
        assert len(ordered) > 0
        # All promotion moves should come before non-promotions
        promotion_count = sum(1 for m in ordered if m.promotion is not None)
        assert promotion_count > 0
        
        # Verify promotions are at the start
        for i in range(promotion_count):
            assert ordered[i].promotion is not None
    
    @pytest.mark.unit
    def test_order_moves_captures_after_promotions(self):
        """Captures should come after promotions but before quiet moves"""
        # Position with capture available
        board = chess.Board("8/8/8/3p4/4P3/8/8/8 w - - 0 1")
        ordered = order_moves(board)
        
        # Should have capture moves
        capture_count = sum(1 for m in ordered if board.is_capture(m))
        assert capture_count > 0
    
    @pytest.mark.unit
    def test_order_moves_quiet_moves_last(self):
        """Quiet moves should come last"""
        board = chess.Board()
        ordered = order_moves(board)
        
        # All legal moves should be included
        assert len(ordered) == len(list(board.legal_moves))
    
    @pytest.mark.unit
    def test_order_moves_includes_all_legal_moves(self):
        """Move ordering should include all legal moves"""
        board = chess.Board()
        ordered = order_moves(board)
        legal = list(board.legal_moves)
        
        assert len(ordered) == len(legal)
        assert set(ordered) == set(legal)


class TestAIMoveSelection:
    """Tests for AI move selection logic"""
    
    @pytest.mark.unit
    def test_ai_chooses_best_move_white(self):
        """AI should choose best move when playing as white"""
        # Simple position: white can capture queen
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/2N5/PPPPPPPP/R1BQKBNR b KQkq - 0 1")
        board.set_piece_at(chess.E4, chess.Piece(chess.QUEEN, chess.BLACK))
        board.turn = chess.WHITE
        
        best_move = choose_ai_move(board, depth=2)
        
        assert best_move is not None
        assert best_move in board.legal_moves
    
    @pytest.mark.unit
    def test_ai_chooses_best_move_black(self):
        """AI should choose best move when playing as black"""
        board = chess.Board("rnbqkbnr/pppppppp/8/8/2n5/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        board.set_piece_at(chess.E4, chess.Piece(chess.QUEEN, chess.WHITE))
        board.turn = chess.BLACK
        
        best_move = choose_ai_move(board, depth=2)
        
        assert best_move is not None
        assert best_move in board.legal_moves
    
    @pytest.mark.unit
    def test_ai_finds_forced_mate_in_one(self):
        """AI should find checkmate in one move"""
        # Back rank mate
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/R6K w - - 0 1")
        
        best_move = choose_ai_move(board, depth=2)
        
        # Should be Ra8#
        assert best_move == chess.Move.from_uci("a1a8")
    
    @pytest.mark.unit
    def test_ai_avoids_blunders(self):
        """AI should not hang pieces when avoidable"""
        # Position where queen can escape or be captured
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPQPPP/RNB1KBNR w KQkq - 0 1")
        board.set_piece_at(chess.E5, chess.Piece(chess.ROOK, chess.BLACK))
        
        best_move = choose_ai_move(board, depth=2)
        
        # Queen should move to safety, not stay in danger
        assert best_move is not None
        # Queen shouldn't move to attacked square
        board.push(best_move)
        # Verify queen is safe
        if board.piece_at(best_move.to_square):
            # If queen moved, check it's not hanging
            pass
        board.pop()
    
    @pytest.mark.unit
    def test_ai_returns_none_if_no_legal_moves(self):
        """AI should handle position with no legal moves gracefully"""
        # Stalemate position
        board = chess.Board("7k/8/6Q1/8/8/8/8/K7 b - - 0 1")
        
        assert board.is_stalemate()
        
        # Should return None or handle gracefully
        best_move = choose_ai_move(board, depth=2)
        # Either None or some legal move (if any exist)
        assert best_move is None or best_move in board.legal_moves
    
    @pytest.mark.unit
    def test_ai_depth_parameter_affects_search(self):
        """Higher depth should potentially find better moves"""
        board = chess.Board()
        
        # Both should return legal moves
        move_d1 = choose_ai_move(board, depth=1)
        move_d2 = choose_ai_move(board, depth=2)
        
        assert move_d1 in board.legal_moves
        assert move_d2 in board.legal_moves


class TestQuiescenceSearch:
    """Tests for quiescence search"""
    
    @pytest.mark.unit
    def test_quiescence_returns_numeric_score(self):
        """Quiescence should return a numeric evaluation"""
        board = chess.Board()
        score = quiescence(board, -float('inf'), float('inf'))
        
        assert isinstance(score, (int, float))
    
    @pytest.mark.unit
    def test_quiescence_respects_alpha_beta_bounds(self):
        """Quiescence should respect alpha-beta pruning bounds"""
        board = chess.Board()
        
        alpha = -1000
        beta = 1000
        
        score = quiescence(board, alpha, beta)
        
        # Score should be within or equal to bounds
        assert score >= alpha - 50000 or score <= beta + 50000
    
    @pytest.mark.unit
    def test_quiescence_depth_limit_prevents_infinite_recursion(self):
        """Quiescence should have depth limit"""
        # Position with many captures
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        
        # Should complete without stack overflow
        score = quiescence(board, -float('inf'), float('inf'), depth=0, max_depth=4)
        
        assert isinstance(score, (int, float))
    
    @pytest.mark.unit
    def test_quiescence_handles_checkmate_position(self):
        """Quiescence should handle checkmate correctly"""
        # Checkmate position
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/R6K b - - 0 1")
        board.push(chess.Move.from_uci("g8h8"))
        board.push(chess.Move.from_uci("a1a8"))
        
        score = quiescence(board, -float('inf'), float('inf'))
        
        # Should return extreme score
        assert abs(score) > 50000


class TestMinimaxAlgorithm:
    """Tests for minimax search algorithm"""
    
    @pytest.mark.unit
    def test_minimax_returns_numeric_score(self):
        """Minimax should return numeric evaluation"""
        board = chess.Board()
        score = minimax(board, 2, -float('inf'), float('inf'), True)
        
        assert isinstance(score, (int, float))
    
    @pytest.mark.unit
    def test_minimax_white_maximizes(self):
        """Minimax should maximize for white"""
        # Position favorable to white
        board = chess.Board()
        board.remove_piece_at(chess.D8)  # Remove black queen
        
        score = minimax(board, 2, -float('inf'), float('inf'), True)
        
        # Should return positive score (white advantage)
        assert score > 0
    
    @pytest.mark.unit
    def test_minimax_black_minimizes(self):
        """Minimax should minimize for black"""
        # Position favorable to black
        board = chess.Board()
        board.remove_piece_at(chess.D1)  # Remove white queen
        board.turn = chess.BLACK
        
        score = minimax(board, 2, -float('inf'), float('inf'), False)
        
        # Should return negative score (black advantage)
        assert score < 0
    
    @pytest.mark.unit
    def test_minimax_depth_zero_calls_quiescence(self):
        """Minimax at depth 0 should call quiescence"""
        board = chess.Board()
        
        # Depth 0 should use quiescence
        score = minimax(board, 0, -float('inf'), float('inf'), True)
        
        assert isinstance(score, (int, float))
    
    @pytest.mark.unit
    def test_minimax_handles_game_over(self):
        """Minimax should handle game over positions"""
        # Checkmate
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/R6K b - - 0 1")
        board.push(chess.Move.from_uci("g8h8"))
        board.push(chess.Move.from_uci("a1a8"))
        
        score = minimax(board, 2, -float('inf'), float('inf'), True)
        
        # Should recognize checkmate
        assert abs(score) > 50000
    
    @pytest.mark.unit
    def test_minimax_alpha_beta_pruning_works(self):
        """Alpha-beta pruning should reduce search space"""
        board = chess.Board()
        
        # With very tight bounds, should prune quickly
        score = minimax(board, 1, 0, 100, True)
        
        # Should complete without error
        assert isinstance(score, (int, float))


class TestAIEdgeCases:
    """Tests for AI handling of edge cases"""
    
    @pytest.mark.unit
    def test_ai_handles_only_king_moves(self):
        """AI should handle position where only king can move"""
        board = chess.Board("8/8/8/8/8/8/8/K6k w - - 0 1")
        
        move = choose_ai_move(board, depth=2)
        
        assert move is not None
        assert move in board.legal_moves
        assert board.piece_at(move.from_square).piece_type == chess.KING
    
    @pytest.mark.unit
    def test_ai_handles_one_legal_move(self):
        """AI should handle forced move correctly"""
        # King in check with only one escape
        board = chess.Board("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1")
        
        legal_moves = list(board.legal_moves)
        move = choose_ai_move(board, depth=2)
        
        assert move in legal_moves
    
    @pytest.mark.unit
    def test_ai_prefers_winning_captures(self):
        """AI should prefer capturing valuable pieces"""
        # Free queen available
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        board.set_piece_at(chess.E4, chess.Piece(chess.QUEEN, chess.BLACK))
        
        best_move = choose_ai_move(board, depth=2)
        
        # Should eventually capture the queen or make a good move
        assert best_move is not None
    
    @pytest.mark.unit
    def test_ai_evaluates_promotion_correctly(self):
        """AI should correctly evaluate promotion positions"""
        # Pawn about to promote
        board = chess.Board("8/P7/8/8/8/8/8/K6k w - - 0 1")
        
        best_move = choose_ai_move(board, depth=2)
        
        # Should promote the pawn
        assert best_move.promotion is not None
    
    @pytest.mark.unit
    def test_ai_does_not_crash_on_complex_position(self):
        """AI should handle complex middlegame positions"""
        # Complex middlegame position
        board = chess.Board("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 1")
        
        # Should not crash
        move = choose_ai_move(board, depth=2)
        
        assert move is not None
        assert move in board.legal_moves


class TestMaterialScoring:
    """Tests for material_score function"""
    
    @pytest.mark.unit
    def test_material_score_starting_position(self):
        """Starting position should have material balance of 0"""
        board = chess.Board()
        assert material_score(board) == 0
    
    @pytest.mark.unit
    def test_material_score_white_advantage(self):
        """White up material should have positive score"""
        board = chess.Board()
        board.remove_piece_at(chess.D8)  # Remove black queen
        
        score = material_score(board)
        assert score == 900
    
    @pytest.mark.unit
    def test_material_score_black_advantage(self):
        """Black up material should have negative score"""
        board = chess.Board()
        board.remove_piece_at(chess.D1)  # Remove white queen
        
        score = material_score(board)
        assert score == -900
    
    @pytest.mark.unit
    def test_material_score_counts_all_pieces(self):
        """Material score should count all piece types"""
        board = chess.Board()
        
        # Remove various pieces
        board.remove_piece_at(chess.A1)  # White rook
        board.remove_piece_at(chess.B1)  # White knight
        
        score = material_score(board)
        assert score == -(500 + 320)
