from flask import render_template, request, jsonify, session
import chess
import random
from models import Game, GameMove, db
from datetime import datetime

from ai import choose_ai_move, material_score, evaluate_board
from helpers import explain_illegal_move, finalize_game, finalize_game_if_over, get_active_game_or_abort, get_game_state, init_game, log_game_action, save_game_state, execute_move

import logging
logger = logging.getLogger(__name__)
import uuid

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

def register_routes(app):

    @app.before_request
    def track_activity():
        if request.endpoint != "static":
            session["last_activity"] = datetime.utcnow().isoformat()
            session.modified = True

    @app.route("/")
    def home():
        # Only clear/init session if:
        # No FEN in session (means this is a fresh start, not a test position restore)
        should_clear = 'fen' not in session
        
        if should_clear:
            session.clear()
            session.modified = True
            init_game()
        # Session FEN will be preserved across requests as long as it exists
        
        # Get current board state to pass to template
        board, move_history, captured_pieces, special_moves = get_game_state()
        initial_position = board.fen()
        
        status = ""
        if board.is_checkmate():
            winner = "White" if board.turn == chess.BLACK else "Black"
            status = f"{winner} wins by Checkmate!"
        elif board.is_check():
            status = "Check!"
        else:
            if board.turn == chess.WHITE:
                status = "White's turn"
            else:
                # Black's turn
                if app.config.get('AI_ENABLED', False):
                    status = "AI is thinking..."
                else:
                    status = "Black's turn"
        
        material = material_score(board)
        evaluation = evaluate_board(board)
        game_over = board.is_checkmate() or board.is_stalemate() or board.is_insufficient_material() or board.is_fifty_moves() or board.is_seventyfive_moves() or board.is_fivefold_repetition()
        
        return render_template("chess.html", 
                             initial_position=initial_position, 
                             status=status,
                             initial_material=material,
                             initial_evaluation=evaluation,
                             initial_move_history=move_history,
                             initial_captured_pieces=captured_pieces,
                             initial_special_moves=special_moves,
                             initial_turn="white" if board.turn == chess.WHITE else "black",
                             ai_enabled=app.config.get('AI_ENABLED', False),
                             initial_game_over=game_over)


    @app.route("/move", methods=["POST"])
    def move():
        move_id = uuid.uuid4().hex[:8]

        board, move_history, captured_pieces, special_moves = get_game_state()
        game, is_active = get_active_game_or_abort()

        logger.info("[%s] /move request received", move_id)

        if game and not is_active:
            logger.info("[%s] Move rejected: game already ended", move_id)
            return jsonify({
                "status": "game_over",
                "message": "This game has already ended.",
                "result": game.result,
                "termination_reason": game.termination_reason,
                "fen": board.fen(),
                "turn": "white" if board.turn == chess.WHITE else "black",
                "check": board.is_check(),
                "checkmate": board.is_checkmate(),
                "stalemate": board.is_stalemate(),
                "fifty_moves": board.is_fifty_moves(),
                "repetition": board.is_repetition(),
                "insufficient_material": board.is_insufficient_material(),
                "game_over": True,
                "move_history": move_history,
                "captured_pieces": captured_pieces,
                "material": material_score(board),
                "evaluation": evaluate_board(board)
            }), 400

        logger.debug("[%s] Session keys: %s", move_id, list(session.keys()))
        logger.debug("[%s] Session FEN: %s", move_id, session.get("fen"))
        logger.debug("[%s] Board FEN: %s", move_id, board.fen())
        logger.debug("[%s] Turn: %s", move_id, "white" if board.turn else "black")

        data = request.get_json()
        from_sq = data.get("from")
        to_sq = data.get("to")
        promotion = data.get("promotion")

        # ✅ ADD THIS: Normalize promotion piece to lowercase (UCI standard)
        if promotion:
            promotion = promotion.lower()

        uci = f"{from_sq}{to_sq}{promotion}" if promotion else f"{from_sq}{to_sq}"
        logger.info("[%s] UCI move received: %s", move_id, uci)

        try:
            move = chess.Move.from_uci(uci)

            if move not in board.legal_moves:
                reason = explain_illegal_move(board, move)
                
                # 🔧 ENHANCED LOGGING FOR ILLEGAL MOVES
                logger.warning(
                    "[%s] Illegal move | uci=%s | reason=%s | fen=%s",
                    move_id,
                    uci,
                    reason,
                    board.fen(),
                )

                logger.debug(
                    "[%s] Legal moves (sample): %s",
                    move_id,
                    [m.uci() for m in list(board.legal_moves)[:10]],
                )

                return jsonify({
                    "status": "illegal",
                    "message": reason,
                    "material": material_score(board),
                    "evaluation": evaluate_board(board)
                })
            
            logger.info("[%s] Legal move accepted", move_id)
            
            # Execute the move
            execute_move(board, move, move_history, captured_pieces, special_moves)

            if move.promotion:
                logger.info(
                    "[%s] Pawn promotion to %s",
                    move_id,
                    chess.piece_name(move.promotion),
                )

            logger.debug("[%s] Board after move: %s", move_id, board.fen())

            #add to the db
            game_id = session.get("game_id")
            game = db.session.get(Game, game_id) if game_id else None

            if game:
                db.session.add(GameMove(
                    game_id=game_id,
                    move_number=len(move_history),
                    color="white",
                    san=move_history[-1],
                    uci=move.uci(),
                    fen_after=board.fen()
                ))
                db.session.commit()
            if game:
                finalize_game_if_over(board, game)
                
            # Clear test position flag if it was set (after first move)
            session.pop('_test_position_set', None)
            
            # Save updated session state
            save_game_state(board, move_history, captured_pieces, special_moves)

            material = material_score(board)
            evaluation = evaluate_board(board)

            logger.info("[%s] Move complete | material=%s | eval=%s", move_id, material, evaluation)

            response_data = {
                "status": "ok",
                "special_moves": special_moves,
                "fen": board.fen(),
                "turn": "white" if board.turn == chess.WHITE else "black",
                "check": board.is_check(),
                "checkmate": board.is_checkmate(),
                "stalemate": board.is_stalemate(),
                "fifty_moves": board.is_fifty_moves(),
                "repetition": board.is_repetition(),
                "insufficient_material": board.is_insufficient_material(),
                "game_over": board.is_checkmate() or board.is_stalemate() or board.is_insufficient_material() or board.is_fifty_moves() or board.is_seventyfive_moves() or board.is_fivefold_repetition(), 
                "move_history": move_history,
                "captured_pieces": captured_pieces,
                "material": material,
                "evaluation": evaluation
            }

            return jsonify(response_data)

        except Exception as e:
            logger.exception("[%s] Exception while processing move", move_id)

            return jsonify({
                "status": "illegal", 
                "message": str(e), 
                "material": material_score(board),
                "evaluation": evaluate_board(board),
                "fen": board.fen(),
                "turn": "white" if board.turn == chess.WHITE else "black",
                "check": board.is_check(),
                "checkmate": board.is_checkmate(),
                "stalemate": board.is_stalemate(),
                "fifty_moves": board.is_fifty_moves(),
                "repetition": board.is_repetition(),
                "insufficient_material": board.is_insufficient_material(),
                "game_over": board.is_checkmate() or board.is_stalemate() or board.is_insufficient_material() or board.is_fifty_moves() or board.is_seventyfive_moves() or board.is_fivefold_repetition(),
                "move_history": move_history,
                "captured_pieces": captured_pieces,
                "special_moves": special_moves
            })

    # ai move route
    @app.route("/ai-move", methods=["POST"])
    def ai_move():
        board, move_history, captured_pieces, special_moves = get_game_state()

        # Only move if game still active
        if board.is_game_over():
            return jsonify({
                "status": "ok",
                "fen": board.fen(),
                "turn": "white" if board.turn == chess.WHITE else "black",
                "game_over": True,
                "move_history": move_history,
                "captured_pieces": captured_pieces,
                "special_moves": special_moves,
                "material": material_score(board),
                "evaluation": evaluate_board(board)
            })

        logger.info("AI move requested")
        try:
            ai_move = choose_ai_move(board, depth=2)
            if ai_move is None:
                logger.error("AI error, falling back to random move", exc_info=True)
                ai_move = random.choice(list(board.legal_moves))
                logger.info(f"AI selected move: {ai_move.uci()}")
        except Exception as e:
            logger.error("ERROR in AI", exc_info=True)
            ai_move = random.choice(list(board.legal_moves))
            logger.info(f"Fallback random move: {ai_move.uci()}")
        
        # Execute the AI move
        execute_move(board, ai_move, move_history, captured_pieces, special_moves, is_ai=True)

        # --- DB LOGGING (AI move) ---
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
        
        if game:
            finalize_game_if_over(board, game)
        # --- END DB LOGGING ---

        save_game_state(board, move_history, captured_pieces, special_moves)

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
            "game_over": board.is_checkmate() or board.is_stalemate() or board.is_insufficient_material() or board.is_fifty_moves() or board.is_seventyfive_moves() or board.is_fivefold_repetition(),
            "move_history": move_history,
            "captured_pieces": captured_pieces,
            "special_moves": special_moves,
            "material": material_score(board),
            "evaluation": evaluate_board(board)
        })

    # reset route
    @app.route("/reset", methods=["POST"])
    def reset():
        logger.info("Game reset requested")
        game_id = session.get("game_id")
        if game_id:
            game = db.session.get(Game, game_id)
            if game and game.ended_at is None:
                finalize_game(game, "*", "abandoned")
        session.clear()  # This also clears _test_position_set flag
        init_game()

        return jsonify({
            "status": "ok",
            "special_moves": [],
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
            "captured_pieces": {'white': [], 'black': []},
            "material": 0,
            "evaluation": 0
        })
    
    # resign route
    @app.route("/resign", methods=["POST"])
    def resign():
        game_id = session.get("game_id")
        if not game_id:
            return jsonify({"status": "error", "message": "No active game"}), 400

        game = db.session.get(Game, game_id)
        if not game or game.ended_at:
            return jsonify({"status": "error", "message": "Game already ended"}), 400

        board, *_ = get_game_state()

        data = request.get_json()
        resigning_color = data.get("color")  # "white" or "black"

        if resigning_color not in ("white", "black"):
            return jsonify({"status": "error", "message": "Invalid color"}), 400

        winner = "black" if resigning_color == "white" else "white"
        result = "1-0" if winner == "white" else "0-1"

        log_game_action(
            game,
            board,
            "[Resignation]"
        )

        finalize_game(game, result, "resignation")
        db.session.commit()
        logger.info("Game resigned by %s", resigning_color)

        session.pop("fen", None)
        session.pop("move_history", None)
        session.pop("captured_pieces", None)
        session.pop("special_moves", None)

        return jsonify({
            "status": "ok",
            "result": result,
            "winner": winner,
            "termination_reason": "resignation",
            "game_over": True
        })
    
    # 50-move rule draw claim
    @app.route("/claim-draw/50-move", methods=["POST"])
    def claim_50_move_draw():
        board, *_ = get_game_state()
        game = db.session.get(Game, session.get("game_id"))

        if not game or game.ended_at:
            return jsonify({"status": "game_over"})

        if not board.is_fifty_moves():
            return jsonify({"status": "invalid", "reason": "not_claimable"})
        
        log_game_action(
            game,
            board,
            "[Draw claimed: 50-move rule]"
        )

        finalize_game(game, "1/2-1/2", "draw_50_move_rule")
        logger.info("Draw claimed by 50-move rule")
        return jsonify({"status": "ok", "result": game.result})
  
    # claim threefold repetition draw
    @app.route("/claim-draw/repetition", methods=["POST"])
    def claim_repetition_draw():
        board, *_ = get_game_state()
        game = db.session.get(Game, session.get("game_id"))

        if not game or game.ended_at:
            return jsonify({"status": "game_over"})

        if not board.can_claim_threefold_repetition():
            return jsonify({"status": "invalid", "reason": "not_claimable"})
        
        log_game_action(
            game,
            board,
            "[Draw claimed: threefold repetition]"
        )

        finalize_game(game, "1/2-1/2", "draw_threefold_repetition")
        logger.info("Draw claimed: threefold repetition")
        return jsonify({"status": "ok", "result": game.result})
    
    #dra agreement route
    @app.route("/draw-agreement", methods=["POST"])
    def draw_agreement():
        board, *_ = get_game_state()
        game = db.session.get(Game, session.get("game_id"))

        if not game or game.ended_at:
            return jsonify({"status": "game_over"})
        
        log_game_action(
            game,
            board,
            "[Draw agreed]"
        )

        finalize_game(game, "1/2-1/2", "draw_by_agreement")
        logger.info("Draw agreed by both players")
        return jsonify({"status": "ok", "result": game.result})

    ###### route for testing purposes only ######
    @app.route("/test/set_position", methods=["POST"])
    def test_set_position():
        """
        TEST-ONLY endpoint to set exact board position
        Allows E2E tests to create specific scenarios
        
        Example: POST /test/set_position
        {
            "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2",
            "move_history": ["e4", "e5"],
            "captured_pieces": {"white": [], "black": []},
            "special_moves": []
        }
        """
        # SECURITY: Only allow in testing mode
        if not app.config.get('TESTING', False):
            return jsonify({"error": "Endpoint only available in testing mode"}), 403
        
        data = request.get_json()
        fen = data.get('fen')
        
        if not fen:
            return jsonify({"error": "FEN required"}), 400
        
        # Validate FEN
        try:
            test_board = chess.Board(fen)
        except ValueError as e:
            return jsonify({"error": f"Invalid FEN: {str(e)}"}), 400
        
        # Create board without castling rights to preserve empty squares
        fen_parts = fen.split()
        castling = fen_parts[2]
        fen_no_castling = fen.replace(castling, '-')
        board = chess.Board(fen_no_castling)
        
        # Set castling rights
        if 'K' in castling:
            board.castling_rights |= chess.BB_H1
        if 'Q' in castling:
            board.castling_rights |= chess.BB_A1
        if 'k' in castling:
            board.castling_rights |= chess.BB_H8
        if 'q' in castling:
            board.castling_rights |= chess.BB_A8
        
        # Set session state
        session['fen'] = board.fen()
        session['move_history'] = data.get('move_history', [])
        session['captured_pieces'] = data.get('captured_pieces', {'white': [], 'black': []})
        session['special_moves'] = data.get('special_moves', [])
        session['_test_position_set'] = True
        
        # Create/update game for this test position
        game_id = session.get("game_id")
        game = db.session.get(Game, game_id) if game_id else None
        
        if not game or game.ended_at:
            # Create new game for this test position
            new_game = Game(ai_enabled=True)
            db.session.add(new_game)
            db.session.commit()
            session['game_id'] = new_game.id
        
        session.modified = True
        
        return jsonify({
            "status": "ok",
            "fen": board.fen(),
            "turn": "white" if board.turn == chess.WHITE else "black",
            "check": board.is_check(),
            "checkmate": board.is_checkmate(),
            "stalemate": board.is_stalemate(),
            "game_over": board.is_game_over(),
            "material": material_score(board),
            "evaluation": evaluate_board(board)
        })