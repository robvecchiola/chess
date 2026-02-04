import chess
import math
from constants import PIECE_TABLES, PIECE_VALUES
import logging
import random

TOP_N_MOVES = 3


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
    
    noise = random.randint(-8, 8)  # centipawns
    return score + noise



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
    logger.debug(
        "AI evaluating position | turn=%s | depth=%s | fen=%s",
        "white" if board.turn else "black",
        depth,
        board.fen()
    )

    # Opening randomness (first 1–2 moves)
    # Intentional: random early move for variety.
    # Mate and promotion are impossible this early.

    #if board.fullmove_number <= 2:
    #    legal = list(board.legal_moves)
    #    if not legal:
    #        logger.error("AI failed to select a move | fen=%s", board.fen())
    #        return None
    #    else:
    #        return random.choice(legal)

    # opening book on the fly
    if board.fullmove_number <= 2:
        scored = []
        for move in board.legal_moves:
            board.push(move)
            score = evaluate_board(board)
            board.pop()
            scored.append((score, move))

        # Sort by score (first element of tuple) in descending order (maximize)
        scored.sort(key=lambda x: x[0], reverse=True)
        return random.choice(scored[:3])[1]

    scored_moves = []

    maximizing_white = board.turn == chess.WHITE

    for move in order_moves(board):
        board.push(move)
        value = minimax(
            board,
            depth - 1,
            -math.inf,
            math.inf,
            not maximizing_white
        )
        board.pop()

        scored_moves.append((value, move))

    if not scored_moves:
        logger.error("AI failed to select a move | fen=%s", board.fen())
        return None

    # Sort best → worst
    scored_moves.sort(
        key=lambda x: x[0],
        reverse=maximizing_white
    )

    # Select among top moves, but ensure list is not empty
    top_moves = scored_moves[:TOP_N_MOVES]
    
    if not top_moves:
        logger.error("No top moves available | fen=%s", board.fen())
        return None
    
    # Among top-scored moves, prefer promotions-to-queen
    best_score = top_moves[0][0]
    tied_moves = [(v, m) for v, m in top_moves if v == best_score]
    
    # Further filter: prefer queen promotions among ties
    queen_promotions = [m for v, m in tied_moves if m.promotion == chess.QUEEN]
    if queen_promotions:
        chosen_move = queen_promotions[0]
    else:
        # No queen promotions in ties; pick randomly among tied moves or first if only one
        if len(tied_moves) > 1:
            chosen_value, chosen_move = random.choice(tied_moves)
        else:
            chosen_value, chosen_move = tied_moves[0]

    logger.info(
        "AI selected move | uci=%s | turn=%s | eval=%s",
        chosen_move.uci(),
        "white" if board.turn else "black",
        best_score
    )

    return chosen_move

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