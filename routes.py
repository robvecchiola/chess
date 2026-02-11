from flask import render_template, request, jsonify, session
import chess
import random
from models import Game, GameMove, db
from datetime import datetime

from ai import choose_ai_move, material_score, evaluate_board
from helpers import explain_illegal_move, finalize_game, finalize_game_if_over, get_active_game_or_abort, get_ai_record, get_game_state, get_or_create_player_uuid, init_game, log_game_action, save_game_state, execute_move, state_response, touch_game

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
            logger.info("Initializing new game session")
            session.clear()
            session.modified = True
            init_game()
        else:
            logger.debug("Loading existing game session | game_id=%s", session.get("game_id"))
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
                             initial_check=board.is_check(),
                             initial_checkmate=board.is_checkmate(),
                             initial_stalemate=board.is_stalemate(),
                             initial_fifty_moves=board.is_fifty_moves(),
                             initial_can_claim_repetition=board.can_claim_threefold_repetition(),
                             initial_insufficient_material=board.is_insufficient_material(),
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
            return state_response(
                status="game_over",
                from_session=True,
                extra={
                    "message": "This game has already ended.",
                    "result": game.result,
                    "termination_reason": game.termination_reason,
                },
                code=400
            )

        logger.debug("[%s] Session keys: %s", move_id, list(session.keys()))
        logger.debug("[%s] Session FEN: %s", move_id, session.get("fen"))
        logger.debug("[%s] Board FEN: %s", move_id, board.fen())
        logger.debug("[%s] Turn: %s", move_id, "white" if board.turn else "black")

        data = request.get_json()
        if data is None:
            logger.warning("[%s] Request has no JSON body", move_id)
            return state_response(
                status="illegal",
                board=board,
                move_history=move_history,
                captured_pieces=captured_pieces,
                special_moves=special_moves,
                extra={"message": "Invalid move format"},
                code=400
            )
        
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

                return state_response(
                    status="illegal",
                    board=board,
                    move_history=move_history,
                    captured_pieces=captured_pieces,
                    special_moves=special_moves,
                    extra={"message": reason},
                    code=400
                )
            
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
                # Determine the color that just moved
                # After board.push(), it's the opponent's turn, so we need the opposite of current turn
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
            if game:
                finalize_game_if_over(board, game)
            if game:
                touch_game(game)
                
            # Clear test position flag if it was set (after first move)
            session.pop('_test_position_set', None)
            
            # Save updated session state
            save_game_state(board, move_history, captured_pieces, special_moves)

            material = material_score(board)
            evaluation = evaluate_board(board)

            logger.info("[%s] Move complete | material=%s | eval=%s", move_id, material, evaluation)

            return state_response(
                status="ok",
                board=board,
                move_history=move_history,
                captured_pieces=captured_pieces,
                special_moves=special_moves,
                extra={
                    "material": material,
                    "evaluation": evaluation,
                }
            )

        except (chess.InvalidMoveError, ValueError) as e:
            logger.warning("[%s] Invalid move format | error=%s", move_id, str(e))

            return state_response(
                status="illegal",
                board=board,
                move_history=move_history,
                captured_pieces=captured_pieces,
                special_moves=special_moves,
                extra={"message": "Invalid move format"},
                code=400
            )
        except Exception as e:
            logger.exception("[%s] Exception while processing move", move_id)

            return state_response(
                status="error",
                board=board,
                move_history=move_history,
                captured_pieces=captured_pieces,
                special_moves=special_moves,
                extra={"message": str(e)},
                code=500
            )

    # ai move route
    @app.route("/ai-move", methods=["POST"])
    def ai_move():

        game_id = session.get("game_id")
        game = db.session.get(Game, game_id) if game_id else None

        board, move_history, captured_pieces, special_moves = get_game_state()

        if game and game.ended_at is not None:
            return state_response(status="game_over", from_session=True, code=400)

        # Only move if game still active
        if board.is_game_over():
            return state_response(
                status="ok",
                board=board,
                move_history=move_history,
                captured_pieces=captured_pieces,
                special_moves=special_moves,
                extra={"game_over": True}
            )

        logger.info("AI move requested | game_id=%s", session.get("game_id"))
        try:
            ai_move = choose_ai_move(board, depth=2)
            if ai_move is None:
                logger.error("AI error, falling back to random move", exc_info=True)
                ai_move = random.choice(list(board.legal_moves))
                logger.info("AI fallback move selected | uci=%s", ai_move.uci())
        except Exception as e:
            logger.error("AI selection failed, falling back to random move", exc_info=True)
            ai_move = random.choice(list(board.legal_moves))
            logger.info("Fallback random move selected | uci=%s", ai_move.uci())
        
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
        if game:
            touch_game(game)
        # --- END DB LOGGING ---

        save_game_state(board, move_history, captured_pieces, special_moves)

        return state_response(
            status="ok",
            board=board,
            move_history=move_history,
            captured_pieces=captured_pieces,
            special_moves=special_moves,
            extra={
                "material": material_score(board),
                "evaluation": evaluate_board(board),
            }
        )

    # reset route
    @app.route("/reset", methods=["POST"])
    def reset():
        game_id = session.get("game_id")
        logger.info("Game reset requested | game_id=%s", game_id)
        if game_id:
            game = db.session.get(Game, game_id)
            if game and game.ended_at is None:
                logger.info("Abandoning active game | game_id=%s", game_id)
                finalize_game(game, "*", "abandoned")
                game.state = "abandoned"
                db.session.commit()
                touch_game(game)
        session.clear()  # This also clears _test_position_set flag
        logger.debug("Session cleared and new game initialized")
        init_game()

        board = chess.Board()
        return state_response(
            status="ok",
            board=board,
            move_history=[],
            captured_pieces={'white': [], 'black': []},
            special_moves=[]
        )
    
    # resign route
    @app.route("/resign", methods=["POST"])
    def resign():
        game_id = session.get("game_id")
        if not game_id:
            logger.warning("Resign attempt without active game")
            return state_response(
                status="error",
                from_session=True,
                extra={"message": "No active game"},
                code=400
            )

        game = db.session.get(Game, game_id)
        if not game or game.ended_at:
            logger.warning("Resign attempt on ended game | game_id=%s", game_id)
            return state_response(
                status="error",
                from_session=True,
                extra={"message": "Game already ended"},
                code=400
            )

        board, move_history, captured_pieces, special_moves = get_game_state()

        data = request.get_json()
        resigning_color = data.get("color")  # "white" or "black"

        if resigning_color not in ("white", "black"):
            logger.warning("Resign attempt with invalid color | color=%s | game_id=%s", resigning_color, game_id)
            return state_response(
                status="error",
                from_session=True,
                extra={"message": "Invalid color"},
                code=400
            )


        winner = "black" if resigning_color == "white" else "white"
        result = "1-0" if winner == "white" else "0-1"

        log_game_action(
            game,
            board,
            "[Resignation]"
        )

        finalize_game(game, result, "resignation")
        db.session.commit()
        if game:
            touch_game(game)
        logger.info("Game resigned | game_id=%s | resigning_color=%s | winner=%s", game_id, resigning_color, winner)

        session.pop("fen", None)
        session.pop("move_history", None)
        session.pop("captured_pieces", None)
        session.pop("special_moves", None)

        return state_response(
            status="ok",
            board=board,
            move_history=move_history,
            captured_pieces=captured_pieces,
            special_moves=special_moves,
            extra={
                "game_over": True,
                "result": result,
                "winner": winner,
                "termination_reason": "resignation"
            }
        )

    # 50-move rule draw claim
    @app.route("/claim-draw/50-move", methods=["POST"])
    def claim_50_move_draw():
        game_id = session.get("game_id")
        board, move_history, captured_pieces, special_moves = get_game_state()
        game = db.session.get(Game, game_id)

        if not game or game.ended_at:
            logger.warning("50-move draw claim on ended game | game_id=%s", game_id)
            return state_response(status="game_over", from_session=True)

        if not board.is_fifty_moves():
            logger.debug("50-move draw claim invalid | game_id=%s | halfmove_clock=%s", game_id, board.halfmove_clock)
            return state_response(status="invalid", from_session=True, extra={"reason": "not_claimable"}, code=400)
        
        log_game_action(
            game,
            board,
            "[Draw claimed: 50-move rule]"
        )

        finalize_game(game, "1/2-1/2", "draw_50_move_rule")
        if game:
            touch_game(game)
        logger.info("Draw claimed by 50-move rule | game_id=%s", game_id)
    
        return state_response(
            status="ok",
            board=board,
            move_history=move_history,
            captured_pieces=captured_pieces,
            special_moves=special_moves,
            extra={
                "game_over": True,
                "result": "1/2-1/2",
                "termination_reason": "draw_50_move_rule"
            }
        )

    # claim threefold repetition draw
    @app.route("/claim-draw/repetition", methods=["POST"])
    def claim_repetition_draw():
        game_id = session.get("game_id")
        board, move_history, captured_pieces, special_moves = get_game_state()
        game = db.session.get(Game, game_id)

        if not game or game.ended_at:
            logger.warning("Repetition draw claim on ended game | game_id=%s", game_id)
            return state_response(status="game_over", from_session=True)

        if not board.can_claim_threefold_repetition():
            logger.debug("Repetition draw claim invalid | game_id=%s", game_id)
            return state_response(status="invalid", from_session=True, extra={"reason": "not_claimable"}, code=400)
        
        log_game_action(
            game,
            board,
            "[Draw claimed: threefold repetition]"
        )

        finalize_game(game, "1/2-1/2", "draw_threefold_repetition")
        if game:
            touch_game(game)
        logger.info("Draw claimed by threefold repetition | game_id=%s", game_id)

        return state_response(
            status="ok",
            board=board,
            move_history=move_history,
            captured_pieces=captured_pieces,
            special_moves=special_moves,
            extra={
                "game_over": True,
                "result": "1/2-1/2",
                "termination_reason": "draw_threefold_repetition"
            }
        )
    
    # draw agreement route
    @app.route("/draw-agreement", methods=["POST"])
    def draw_agreement():
        game_id = session.get("game_id")
        board, move_history, captured_pieces, special_moves = get_game_state()
        game = db.session.get(Game, game_id)

        if not game or game.ended_at:
            logger.warning("Draw agreement on ended game | game_id=%s", game_id)
            return state_response(status="game_over", from_session=True)
        
        log_game_action(
            game,
            board,
            "[Draw agreed]"
        )

        finalize_game(game, "1/2-1/2", "draw_by_agreement")
        if game:
            touch_game(game)
        logger.info("Draw agreed by both players | game_id=%s", game_id)
    
        return state_response(
            status="ok",
            board=board,
            move_history=move_history,
            captured_pieces=captured_pieces,
            special_moves=special_moves,
            extra={
                "game_over": True,
                "result": "1/2-1/2",
                "termination_reason": "draw_by_agreement"
            }
        )
    
    ##### route to get AI record ######
    @app.route("/stats/ai-record")
    def ai_record():
        return get_ai_record()

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
            logger.warning("Test endpoint /test/set_position accessed outside testing mode")
            return jsonify({"error": "Endpoint only available in testing mode"}), 403
        
        data = request.get_json()
        fen = data.get('fen')
        
        if not fen:
            logger.warning("Test set_position: FEN not provided")
            return jsonify({"error": "FEN required"}), 400
        
        # Validate FEN
        try:
            test_board = chess.Board(fen)
            logger.debug("[TEST] Setting board position | fen=%s", fen)
        except ValueError as e:
            logger.error("[TEST] Invalid FEN provided | fen=%s | error=%s", fen, str(e))
            return jsonify({"error": f"Invalid FEN: {str(e)}"}), 400
        
        # Use the provided FEN directly to preserve castling and en-passant
        # information exactly as the test supplied it. Creating a board from
        # the canonical FEN is more reliable than attempting to set
        # castling rights manually via bitboards.
        board = chess.Board(fen)
        
        # Set session state
        # Store the exact FEN supplied by tests so session reflects the
        # intended position (including castling rights and ep square).
        session['fen'] = fen
        session['move_history'] = data.get('move_history', [])
        session['captured_pieces'] = data.get('captured_pieces', {'white': [], 'black': []})
        session['special_moves'] = data.get('special_moves', [])
        session['_test_position_set'] = True
        
        # Create/update game for this test position
        game_id = session.get("game_id")
        game = db.session.get(Game, game_id) if game_id else None
        
        if not game or game.ended_at:
            # Create new game for this test position
            new_game = Game(
                ai_enabled=True,
                player_uuid=get_or_create_player_uuid(),
                state="active",
                last_activity_at=datetime.utcnow(),
            )
            db.session.add(new_game)
            db.session.commit()
            session['game_id'] = new_game.id
            logger.debug("[TEST] Created new test game | game_id=%s", new_game.id)
        else:
            logger.debug("[TEST] Reusing existing test game | game_id=%s", game.id)
        
        session.modified = True
        
        return state_response(
            status="ok",
            board=board,
            move_history=session.get("move_history", []),
            captured_pieces=session.get("captured_pieces", {'white': [], 'black': []}),
            special_moves=session.get("special_moves", []),
        )