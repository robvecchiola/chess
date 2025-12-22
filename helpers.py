from flask import session
import chess
# -------------------------------------------------------------------
# Session Helpers
# -------------------------------------------------------------------

def init_game():
    session['fen'] = chess.STARTING_FEN
    session['move_history'] = []
    session['captured_pieces'] = {'white': [], 'black': []}


def get_game_state():
    if 'fen' not in session or session['fen'] is None:
        init_game()

    board = chess.Board(session['fen'])
    move_history = session.get('move_history', [])
    captured_pieces = session.get('captured_pieces', {'white': [], 'black': []})

    return board, move_history, captured_pieces


def save_game_state(board, move_history, captured_pieces):
    session['fen'] = board.fen()
    session['move_history'] = move_history
    session['captured_pieces'] = captured_pieces