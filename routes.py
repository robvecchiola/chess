from flask import render_template, request, jsonify, session
import chess
import random

from helpers import get_game_state, init_game, save_game_state

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

def register_routes(app):

    @app.route("/")
    def home():
        session.clear()
        session.modified = True
        init_game()
        return render_template("chess.html")


    @app.route("/move", methods=["POST"])
    def move():
        board, move_history, captured_pieces = get_game_state()

        print("\n--- DEBUG ---")
        print("Current board FEN:", board.fen())
        print("Current turn:", "white" if board.turn == chess.WHITE else "black")

        data = request.get_json()
        from_sq = data.get("from")
        to_sq = data.get("to")
        promotion = data.get("promotion")

        uci = f"{from_sq}{to_sq}{promotion}" if promotion else f"{from_sq}{to_sq}"
        print("Move received:", uci)

        try:
            move = chess.Move.from_uci(uci)

            if move not in board.legal_moves:
                print("Move is illegal")
                return jsonify({"status": "illegal", "fen": board.fen()})

            # SAN before push
            move_san = board.san(move)

            # Track player capture
            if board.is_capture(move):
                if board.is_en_passant(move):
                    captured_piece = chess.Piece(chess.PAWN, not board.turn)
                else:
                    captured_piece = board.piece_at(move.to_square)

                if captured_piece:
                    # Store by capturing player: white piece captured → black captured it
                    color_key = "black" if captured_piece.color == chess.WHITE else "white"
                    captured_pieces[color_key].append(captured_piece.symbol())
                    print("Player captured:", captured_piece.symbol())

            board.push(move)
            move_history.append(move_san)

            # -----------------------------------------------------------
            # AI Move
            # -----------------------------------------------------------
            if app.config.get("AI_ENABLED", True) and not board.is_game_over():
                ai_move = random.choice(list(board.legal_moves))
                ai_san = board.san(ai_move)

                if board.is_capture(ai_move):
                    if board.is_en_passant(ai_move):
                        captured_piece = chess.Piece(chess.PAWN, not board.turn)
                    else:
                        captured_piece = board.piece_at(ai_move.to_square)

                    if captured_piece:
                        # Store by capturing player: white piece captured → black captured it
                        color_key = "black" if captured_piece.color == chess.WHITE else "white"
                        captured_pieces[color_key].append(captured_piece.symbol())
                        print("AI captured:", captured_piece.symbol())

                board.push(ai_move)
                move_history.append(ai_san)

            # Save updated session state
            save_game_state(board, move_history, captured_pieces)

            print("Board after moves:", board.fen())
            print("--- END DEBUG ---\n")

            return jsonify({
                "status": "ok",
                "fen": board.fen(),
                "turn": "white" if board.turn == chess.WHITE else "black",
                "check": board.is_check(),
                "checkmate": board.is_checkmate(),
                "stalemate": board.is_stalemate(),
                "fifty_moves": board.is_fifty_moves(),
                "repetition": board.is_repetition(),
                "insufficient_material": board.is_insufficient_material(),
                "game_over": board.is_game_over(),
                "move_history": move_history,
                "captured_pieces": captured_pieces
            })

        except Exception as e:
            print("ERROR:", e)
            return jsonify({"status": "illegal", "message": str(e)})


    @app.route("/reset", methods=["POST"])
    def reset():
        session.clear()
        init_game()

        return jsonify({
            "status": "ok",
            "fen": chess.STARTING_FEN,
            "turn": "white",
            "check": False,
            "checkmate": False,
            "stalemate": False,
            "fifty_moves": False,
            "repetition": False,
            "insufficient_material": False,
            "game_over": False,
            "move_history": [],
            "captured_pieces": {'white': [], 'black': []}
        })