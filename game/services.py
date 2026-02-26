import chess
from flask import session
from models import Game, GameMove, db
from helpers import (
    execute_move,
    save_game_state,
    finalize_game,
    finalize_game_if_over,
    touch_game,
    log_game_action,
)
from datetime import datetime

import logging
logger = logging.getLogger(__name__)


class GameService:

    @staticmethod
    def get_game():
        game_id = session.get("game_id")
        return db.session.get(Game, game_id) if game_id else None

    # -------------------------
    # PLAYER MOVE
    # -------------------------

    @staticmethod
    def process_player_move(board, move, move_history, captured_pieces, special_moves):
        execute_move(board, move, move_history, captured_pieces, special_moves)

        game = GameService.get_game()

        logger.info(
            "event=player_move_applied game_id=%s move=%s fen=%s",
            game.id if game else None,
            move.uci(),
            board.fen()
        )

        if game:
            move_color = "white" if board.turn == chess.BLACK else "black"

            db.session.add(GameMove(
                game_id=game.id,
                move_number=len(move_history),
                color=move_color,
                san=move_history[-1],
                uci=move.uci(),
                fen_after=board.fen()
            ))

            finalize_game_if_over(board, game)
            if game.ended_at:
                logger.info(
                    "event=game_ended game_id=%s result=%s reason=%s",
                    game.id,
                    game.result,
                    game.termination_reason
                )
            touch_game(game)
            db.session.commit()

        save_game_state(board, move_history, captured_pieces, special_moves)

    # -------------------------
    # AI MOVE
    # -------------------------

    @staticmethod
    def process_ai_move(board, move_history, captured_pieces, special_moves, ai_move):
        execute_move(board, ai_move, move_history, captured_pieces, special_moves, is_ai=True)

        game = GameService.get_game()

        logger.info(
            "event=ai_move_applied game_id=%s move=%s fen=%s",
            game.id if game else None,
            ai_move.uci(),
            board.fen()
        )

        if game:
            db.session.add(GameMove(
                game_id=game.id,
                move_number=len(move_history),
                color="black",
                san=move_history[-1],
                uci=ai_move.uci(),
                fen_after=board.fen()
            ))

            finalize_game_if_over(board, game)
            if game.ended_at:
                logger.info(
                    "event=game_ended game_id=%s result=%s reason=%s",
                    game.id,
                    game.result,
                    game.termination_reason
                )
            touch_game(game)
            db.session.commit()

        save_game_state(board, move_history, captured_pieces, special_moves)

    # -------------------------
    # RESIGNATION
    # -------------------------

    @staticmethod
    def resign(board, resigning_color):
        game = GameService.get_game()
        if not game or game.ended_at:
            return None

        winner = "black" if resigning_color == "white" else "white"
        result = "1-0" if winner == "white" else "0-1"

        log_game_action(game, board, "[Resignation]")
        finalize_game(game, result, "resignation")
        touch_game(game)

        logger.info(
            "event=game_resigned game_id=%s resigning_color=%s winner=%s",
            game.id,
            resigning_color,
            winner
        )

        db.session.commit()

        return result, winner

    # -------------------------
    # DRAW CLAIM
    # -------------------------

    @staticmethod
    def claim_draw(board, termination_reason, result="1/2-1/2"):
        game = GameService.get_game()
        if not game or game.ended_at:
            return None

        # Humanize termination reason for logs / move entries
        human_map = {
            "draw_50_move_rule": "50-move rule",
            "draw_threefold_repetition": "threefold repetition",
            "draw_by_agreement": "agreed",
            "draw_75_move_rule": "75-move rule",
            "draw_fivefold_rule": "fivefold repetition",
        }

        if termination_reason == "draw_by_agreement":
            label = "[Draw agreed]"
        else:
            readable = human_map.get(termination_reason, termination_reason)
            label = f"[Draw claimed: {readable}]"

        log_game_action(game, board, label)
        finalize_game(game, result, termination_reason)
        logger.info(
            "event=draw_claimed game_id=%s result=%s reason=%s",
            game.id,
            result,
            termination_reason
        )
        touch_game(game)
        db.session.commit()

        return {
            "result": result,
            "termination_reason": termination_reason
        }

    # -------------------------
    # ABANDON GAME
    # -------------------------

    @staticmethod
    def abandon_game():
        game = GameService.get_game()
        if game and game.ended_at is None:
            finalize_game(game, "*", "abandoned")
            game.state = "abandoned"
            touch_game(game)
            logger.info(
                "event=game_abandoned game_id=%s",
                game.id
            )
            db.session.commit()

    #-------------------------
    # game active check
    #-------------------------
    @staticmethod
    def ensure_active_game():
        game = GameService.get_game()
        if not game or game.ended_at:
            return None
        return game