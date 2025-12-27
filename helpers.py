from flask import session
import chess
# -------------------------------------------------------------------
# Session Helpers
# -------------------------------------------------------------------

def init_game():
    session['fen'] = chess.STARTING_FEN
    session['move_history'] = []
    session['captured_pieces'] = {'white': [], 'black': []}
    session['special_moves'] = []


def get_game_state():
    if 'fen' not in session or session['fen'] is None:
        init_game()

    board = chess.Board()
    move_history = session.get('move_history', [])
    if move_history:
        for san in move_history:
            board.push_san(san)
    else:
        board = chess.Board(session['fen'])
    captured_pieces = session.get('captured_pieces', {'white': [], 'black': []})
    special_moves = session.get('special_moves', [])

    return board, move_history, captured_pieces, special_moves


def save_game_state(board, move_history, captured_pieces, special_moves):
    session['fen'] = board.fen()
    session['move_history'] = move_history
    session['captured_pieces'] = captured_pieces
    session['special_moves'] = special_moves

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