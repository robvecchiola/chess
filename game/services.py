import chess
from flask import session
from models import Game, GameMove, db
from helpers import (
    execute_move,
    save_game_state,
    finalize_game_if_over,
    touch_game,
)

def process_player_move(board, move, move_history, captured_pieces, special_moves):
    """
    Executes and persists a player move.
    Returns updated board state + evaluation data.
    """

    execute_move(board, move, move_history, captured_pieces, special_moves)

    game_id = session.get("game_id")
    game = db.session.get(Game, game_id) if game_id else None

    if game:
        move_color = "white" if board.turn == chess.BLACK else "black"

        db.session.add(GameMove(
            game_id=game_id,
            move_number=len(move_history),
            color=move_color,
            san=move_history[-1],
            uci=move.uci(),
            fen_after=board.fen()
        ))
        db.session.commit()

        finalize_game_if_over(board, game)
        touch_game(game)

    save_game_state(board, move_history, captured_pieces, special_moves)

    return board


def process_ai_move(board, move_history, captured_pieces, special_moves, ai_move):
    execute_move(board, ai_move, move_history, captured_pieces, special_moves, is_ai=True)

    game_id = session.get("game_id")
    game = db.session.get(Game, game_id) if game_id else None

    if game:
        db.session.add(GameMove(
            game_id=game_id,
            move_number=len(move_history),
            color="black",
            san=move_history[-1],
            uci=ai_move.uci(),
            fen_after=board.fen()
        ))
        db.session.commit()

        finalize_game_if_over(board, game)
        touch_game(game)

    save_game_state(board, move_history, captured_pieces, special_moves)

    return board