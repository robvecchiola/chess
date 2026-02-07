from datetime import datetime, timezone
import uuid
from flask import session
from sqlalchemy import case, case, func
from ai import evaluate_board, material_score
from extensions import db
import chess

from models import Game, GameMove
import logging

logger = logging.getLogger(__name__)
# -------------------------------------------------------------------
# Session Helpers
# -------------------------------------------------------------------

def init_game():
    board = chess.Board()

    player_uuid = get_or_create_player_uuid()
    now = datetime.now(timezone.utc)

    game = Game(
        ai_enabled=True,
        player_uuid=player_uuid,
        state="active",
        last_activity_at=now,
    )

    db.session.add(game)
    db.session.commit()

    logger.info(
        "New game initialized | game_id=%s | player_uuid=%s",
        game.id,
        player_uuid,
    )

    session["game_id"] = game.id
    session["fen"] = board.fen()
    session["move_history"] = []
    session["captured_pieces"] = {"white": [], "black": []}
    session["special_moves"] = []
    session.modified = True



def get_game_state():
    if 'fen' not in session or session['fen'] is None:
        init_game()

    move_history = session.get('move_history', [])
    captured_pieces = session.get('captured_pieces', {'white': [], 'black': []})
    if not isinstance(captured_pieces, dict):
        captured_pieces = {'white': [], 'black': []}
    special_moves = session.get('special_moves', [])

    # Try to create board from FEN, fallback to starting position if invalid
    try:
        board = chess.Board(session.get('fen', chess.STARTING_FEN))
    except ValueError:
        logger.warning("Invalid FEN in session, resetting board")
        board = chess.Board()

    # Try to rebuild from move history for position history (repetition detection)
    if move_history:
        try:
            temp_board = chess.Board()
            for san in move_history:
                temp_board.push_san(san)
            board = temp_board
        except Exception as e:
            logger.debug("Failed to rebuild board from move history | error=%s", e)
            pass

    return board, move_history, captured_pieces, special_moves


def save_game_state(board, move_history, captured_pieces, special_moves):
    session['fen'] = board.fen()
    session['move_history'] = move_history
    session['captured_pieces'] = captured_pieces
    session['special_moves'] = special_moves

    logger.debug("Game state saved | fen=%s", board.fen())
    session.modified = True


def execute_move(board, move, move_history, captured_pieces, special_moves, is_ai=False):
    """
    Execute a move on the board, updating history, captures, and special moves.
    For AI moves, apply promotion safety net if needed.
    
    🔑 CRITICAL: Special moves are prefixed with "White:" or "Black:" to allow
    frontend to correctly separate them in UI (#special-white vs #special-black)
    """

    logger.debug(
        "Executing move | uci=%s | ai=%s",
        move.uci(),
        is_ai
    )

    # 🔑 Determine who is making the move BEFORE board state changes
    moving_color = "White" if board.turn == chess.WHITE else "Black"

    # Detect special move
    special_move = None
    if board.is_castling(move):
        special_move = "Castling"
    elif board.is_en_passant(move):
        special_move = "En Passant"
    elif move.promotion:
        special_move = f"Promotion to {chess.piece_symbol(move.promotion).upper()}"
    
    if special_move:
        logger.info("Special move executed | type=%s | color=%s", special_move, moving_color)
    
    # SAN before push
    move_san = board.san(move)

    # Track capture
    if board.is_capture(move):
        if board.is_en_passant(move):
            captured_piece = chess.Piece(chess.PAWN, not board.turn)
        else:
            captured_piece = board.piece_at(move.to_square)

        if captured_piece:
            # Store by capturing player: white piece captured → black captured it
            color_key = "black" if captured_piece.color == chess.WHITE else "white"
            captured_pieces[color_key].append(captured_piece.symbol())

    # For AI: Force promotion if pawn reaches last rank without promotion
    if is_ai and (
        board.piece_at(move.from_square)
        and board.piece_at(move.from_square).piece_type == chess.PAWN
        and chess.square_rank(move.to_square) in (0, 7)
        and move.promotion is None
    ):
        move = chess.Move(
            move.from_square,
            move.to_square,
            promotion=chess.QUEEN
        )
        special_move = "Promotion to Q"

    board.push(move)
    move_history.append(move_san)
    if special_move:
        # 🔑 Prefix with color so frontend can separate white/black moves
        prefixed_special_move = f"{moving_color}: {special_move}"
        special_moves.append(prefixed_special_move)
        logger.debug("Special move appended | prefixed=%s", prefixed_special_move)


## illegal moves helper

def explain_illegal_move(board, move):
    """
    Provide detailed, user-friendly explanations for why a move is illegal.
    Returns a helpful error message string.
    """
    from_square = move.from_square
    to_square = move.to_square
    piece = board.piece_at(from_square)
    
    # 1. No piece at source square
    if piece is None:
        return "There's no piece on that square."
    
    # 2. Wrong color piece
    if piece.color != board.turn:
        color_name = "white" if board.turn == chess.WHITE else "black"
        return f"It's {color_name}'s turn — you can't move your opponent's pieces."
    
    # 3. Move not even pseudo-legal (wrong movement pattern for piece type)
    if not board.is_pseudo_legal(move):
        piece_name = chess.piece_name(piece.piece_type).capitalize()
        
        # Special cases for common mistakes
        if piece.piece_type == chess.PAWN:
            from_file = chess.square_file(from_square)
            to_file = chess.square_file(to_square)
            from_rank = chess.square_rank(from_square)
            to_rank = chess.square_rank(to_square)
            
            # Pawn trying to move backwards
            if piece.color == chess.WHITE and to_rank < from_rank:
                return "Pawns can't move backwards."
            if piece.color == chess.BLACK and to_rank > from_rank:
                return "Pawns can't move backwards."
            
            # Pawn trying to capture straight ahead
            if from_file == to_file and board.piece_at(to_square) is not None:
                return "Pawns can't capture straight ahead — they must capture diagonally."
            
            # Pawn trying to move diagonally without capturing
            if from_file != to_file and board.piece_at(to_square) is None:
                # Check if it's a valid en passant opportunity
                if move != board.ep_square:
                    return "Pawns can only move diagonally when capturing."
            
            # Pawn trying to move too far
            rank_diff = abs(to_rank - from_rank)
            if rank_diff > 2:
                return "Pawns can only move 1-2 squares forward."
            if rank_diff == 2:
                starting_rank = 1 if piece.color == chess.WHITE else 6
                if from_rank != starting_rank:
                    return "Pawns can only move 2 squares on their first move."
        
        elif piece.piece_type == chess.KNIGHT:
            return "Knights move in an 'L' shape: 2 squares in one direction, then 1 square perpendicular."
        
        elif piece.piece_type == chess.BISHOP:
            return "Bishops can only move diagonally."
        
        elif piece.piece_type == chess.ROOK:
            return "Rooks can only move horizontally or vertically."
        
        elif piece.piece_type == chess.QUEEN:
            return "Queens can move horizontally, vertically, or diagonally."
        
        elif piece.piece_type == chess.KING:
            from_file = chess.square_file(from_square)
            to_file = chess.square_file(to_square)
            
            # Check if it's attempted castling
            if abs(to_file - from_file) == 2:
                return "You can't castle right now. Check castling requirements."
            else:
                return "Kings can only move one square in any direction."
        
        return f"{piece_name}s can't move like that."
    
    # 4. Path is blocked (for non-knights)
    if piece.piece_type != chess.KNIGHT:
        # Check if there are pieces in the way
        from_file = chess.square_file(from_square)
        from_rank = chess.square_rank(from_square)
        to_file = chess.square_file(to_square)
        to_rank = chess.square_rank(to_square)
        
        # Calculate direction
        file_step = 0 if to_file == from_file else (1 if to_file > from_file else -1)
        rank_step = 0 if to_rank == from_rank else (1 if to_rank > from_rank else -1)
        
        # Check squares along the path
        current_file = from_file + file_step
        current_rank = from_rank + rank_step
        
        while current_file != to_file or current_rank != to_rank:
            check_square = chess.square(current_file, current_rank)
            if board.piece_at(check_square) is not None:
                return "That path is blocked by another piece."
            current_file += file_step
            current_rank += rank_step
    
    # 5. Trying to capture own piece
    target_piece = board.piece_at(to_square)
    if target_piece and target_piece.color == piece.color:
        return "You can't capture your own pieces."
    
    # 6. Move would leave/put king in check
    if board.is_into_check(move):
        if board.is_check():
            return "That move doesn't get your king out of check."
        else:
            # King would be in check after this move (pin or discovered check)
            if piece.piece_type == chess.KING:
                return "You can't move your king into check."
            else:
                return "That move would put your king in check (piece is pinned)."
    
    # 7. Castling-specific issues
    if piece.piece_type == chess.KING:
        from_file = chess.square_file(from_square)
        to_file = chess.square_file(to_square)
        
        if abs(to_file - from_file) == 2:  # Attempting to castle
            if board.is_check():
                return "You can't castle while in check."
            
            # Check if king has moved
            if piece.color == chess.WHITE:
                if not board.has_kingside_castling_rights(chess.WHITE) and not board.has_queenside_castling_rights(chess.WHITE):
                    return "You can't castle because your king has already moved."
            else:
                if not board.has_kingside_castling_rights(chess.BLACK) and not board.has_queenside_castling_rights(chess.BLACK):
                    return "You can't castle because your king has already moved."
            
            # Check if rook has moved
            is_kingside = to_file > from_file
            if is_kingside:
                if piece.color == chess.WHITE and not board.has_kingside_castling_rights(chess.WHITE):
                    return "You can't castle kingside because your rook has moved."
                if piece.color == chess.BLACK and not board.has_kingside_castling_rights(chess.BLACK):
                    return "You can't castle kingside because your rook has moved."
            else:
                if piece.color == chess.WHITE and not board.has_queenside_castling_rights(chess.WHITE):
                    return "You can't castle queenside because your rook has moved."
                if piece.color == chess.BLACK and not board.has_queenside_castling_rights(chess.BLACK):
                    return "You can't castle queenside because your rook has moved."
            
            # Check if squares between king and rook are under attack
            return "You can't castle through or into check."
    
    # 8. Generic fallback
    return "That's not a legal move in this position."


def finalize_game(game, result, reason):
    if game.ended_at is not None:
        logger.debug("Game already finalized | game_id=%s", game.id)
        return

    now = datetime.now(timezone.utc)

    logger.info(
        "Game finalized | game_id=%s | result=%s | reason=%s",
        game.id,
        result,
        reason
    )

    game.result = result
    game.termination_reason = reason
    game.ended_at = now
    game.state = "finished"
    game.last_activity_at = now

    db.session.commit()

def finalize_game_if_over(board, game):
    """
    Finalizes the game if the board is in a game-over state.
    Retrns True if the game was finalized, False otherwise.
        """

    if board.is_checkmate():
         # board.turn is the LOSER after checkmate
        winner = "white" if board.turn == chess.BLACK else "black"
        result = "1-0" if winner == "white" else "0-1"
        reason = "checkmate"

    elif board.is_stalemate():
        result = "1/2-1/2"
        reason = "stalemate"

    elif board.is_insufficient_material():
        result = "1/2-1/2"
        reason = "insufficient_material"

    elif board.is_seventyfive_moves():
        result = "1/2-1/2"
        reason = "draw_75_move_rule"

    elif board.is_fivefold_repetition():
        result = "1/2-1/2"
        reason = "draw_fivefold_rule"

    else:
        return False

    finalize_game(game, result, reason)

    logger.info(
        "Game over detected | game_id=%s | reason=%s",
        game.id,
        reason
    )
    return True


# Active Game Retrieval
def get_active_game_or_abort():
    game_id = session.get("game_id")
    if not game_id:
        return None, None

    game = db.session.get(Game, game_id)
    if not game:
        return None, None

    if game.state != "active":
        return game, False

    return game, True


#log game actions resign and clams
def log_game_action(game, board, label):
    last_move = (
        GameMove.query
        .filter_by(game_id=game.id)
        .order_by(GameMove.move_number.desc())
        .first()
    )

    next_number = (last_move.move_number + 1) if last_move else 1

    db.session.add(GameMove(
        game_id=game.id,
        move_number=next_number,
        color="white" if board.turn == chess.WHITE else "black",
        san=label,
        uci=None,
        fen_after=board.fen()
    ))
    db.session.commit()

    logger.info(
        "Game action logged | game_id=%s | action=%s",
        game.id,
        label
    )

# create player uuid
def get_or_create_player_uuid():
    if "player_uuid" not in session:
        session["player_uuid"] = str(uuid.uuid4())
        session.modified = True
    return session["player_uuid"]


# update last move date/time
def touch_game(game):
    game.last_activity_at = datetime.now(timezone.utc)
    db.session.commit()

# get the ai record against human players
def get_ai_record():
    rows = (
        db.session.query(
            func.sum(case((Game.result == "0-1", 1), else_=0)).label("wins"),
            func.sum(case((Game.result == "1-0", 1), else_=0)).label("losses"),
            func.sum(case((Game.result == "1/2-1/2", 1), else_=0)).label("draws"),
        )
        .filter(Game.ai_enabled.is_(True))
        .filter(Game.ended_at.isnot(None))
        .one()
    )

    wins = rows.wins or 0
    losses = rows.losses or 0
    draws = rows.draws or 0

    total = wins + losses + draws
    win_rate = round((wins / total) * 100, 1) if total else 0.0

    return {
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": win_rate,
        "total": total
    }

def build_full_state(board, move_history, captured_pieces, special_moves):
    return {
        "fen": board.fen(),
        "turn": "white" if board.turn == chess.WHITE else "black",
        "check": board.is_check(),
        "checkmate": board.is_checkmate(),
        "stalemate": board.is_stalemate(),
        "fifty_moves": board.is_fifty_moves(),
        "can_claim_repetition": board.can_claim_threefold_repetition(),
        "insufficient_material": board.is_insufficient_material(),
        "move_history": move_history,
        "captured_pieces": captured_pieces,
        "special_moves": special_moves,
        "material": material_score(board),
        "evaluation": evaluate_board(board),
        "game_over": board.is_game_over()
    }
