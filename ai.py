import chess
import math
from constants import PIECE_TABLES, PIECE_VALUES
import logging

logger = logging.getLogger(__name__)

def evaluate_board(board):
    if board.is_checkmate():
        return -99999 if board.turn else 99999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    
    # Material and positional evaluation
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            value = PIECE_VALUES[piece.piece_type]
            table = PIECE_TABLES[piece.piece_type]
            
            if piece.color == chess.WHITE:
                score += value + table[square]
            else:
                score -= value + table[chess.square_mirror(square)]
    
    return score


def quiescence(board, alpha, beta, depth=0, max_depth=4):
    """Quiescence search to handle captures and checks"""
    stand_pat = evaluate_board(board)
    
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat
    
    # Limit quiescence depth to prevent infinite recursion
    if depth >= max_depth:
        return alpha
    
    # Only consider captures and check evasions
    for move in board.legal_moves:
        if board.is_capture(move) or board.gives_check(move):
            board.push(move)
            score = -quiescence(board, -beta, -alpha, depth + 1, max_depth)
            board.pop()
            
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
    
    return alpha


def minimax(board, depth, alpha, beta, maximizing_white):
    """Minimax from white's perspective (maximizing_white=True means white's turn)"""
    if depth == 0:
        return quiescence(board, alpha, beta)
    
    if board.is_game_over():
        return evaluate_board(board)

    if maximizing_white:
        max_eval = -math.inf
        for move in board.legal_moves:
            board.push(move)
            eval = minimax(board, depth - 1, alpha, beta, False)
            board.pop()
            max_eval = max(max_eval, eval)
            alpha = max(alpha, eval)
            if beta <= alpha:
                break
        return max_eval
    else:
        min_eval = math.inf
        for move in board.legal_moves:
            board.push(move)
            eval = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            min_eval = min(min_eval, eval)
            beta = min(beta, eval)
            if beta <= alpha:
                break
        return min_eval


def order_moves(board):
    """Move ordering: promotions > captures > others"""
    promotions = []
    captures = []
    others = []

    for move in board.legal_moves:
        if move.promotion is not None:
            promotions.append(move)
        elif board.is_capture(move):
            captures.append(move)
        else:
            others.append(move)

    return promotions + captures + others


def choose_ai_move(board, depth=2):
    """Choose the best move using minimax with alpha-beta pruning"""
    # Note: depth=2 with quiescence search is roughly equivalent to depth=3-4 without it
    logger.debug(
        "AI evaluating position | turn=%s | depth=%s | fen=%s",
        "white" if board.turn else "black",
        depth,
        board.fen()
    )

    best_move = None
    
    # Determine if current player is white (maximizing) or black (minimizing)
    if board.turn == chess.WHITE:
        # White wants to maximize
        best_value = -math.inf
        for move in order_moves(board):
            board.push(move)
            value = minimax(board, depth - 1, -math.inf, math.inf, False)
            board.pop()
            
            if value > best_value:
                best_value = value
                best_move = move
    else:
        # Black wants to minimize
        best_value = math.inf
        for move in order_moves(board):
            board.push(move)
            value = minimax(board, depth - 1, -math.inf, math.inf, True)
            board.pop()
            
            if value < best_value:
                best_value = value
                best_move = move
    
    if best_move is None:
        logger.error("AI failed to select a move | fen=%s", board.fen())
    else:
        logger.info(
            "AI selected move | uci=%s | turn=%s",
            best_move.uci(),
            "white" if board.turn else "black",
        )

    return best_move

#material thing
def material_score(board):
    """
    Returns material balance in centipawns.
    Positive = white ahead, negative = black ahead
    """
    score = 0
    for piece_type, value in PIECE_VALUES.items():
        score += len(board.pieces(piece_type, chess.WHITE)) * value
        score -= len(board.pieces(piece_type, chess.BLACK)) * value
    return score