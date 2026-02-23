import chess

from app import create_app
from config import TestingConfig
from game.services import GameService
from extensions import db


app = create_app(TestingConfig)


def test_gameservice_resign_returns_none_when_no_active_game():
    with app.test_request_context():
        result = GameService.resign(chess.Board(), "white")
        assert result is None


def test_gameservice_process_ai_move_without_game_still_saves_session_state():
    with app.test_request_context():
        board = chess.Board()
        move_history = []
        captured_pieces = {"white": [], "black": []}
        special_moves = []

        ai_move = chess.Move.from_uci("e2e4")
        GameService.process_ai_move(board, move_history, captured_pieces, special_moves, ai_move)

        from flask import session
        assert len(move_history) == 1
        assert session.get("fen") == board.fen()


def test_gameservice_abandon_game_noop_without_active_game():
    with app.test_request_context():
        # Should not raise even when no game_id is present in session.
        GameService.abandon_game()
        assert GameService.get_game() is None
