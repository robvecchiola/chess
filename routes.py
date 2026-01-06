from flask import render_template, request, jsonify, session
import chess
import random
from models import Game, GameMove, db

from ai import choose_ai_move, material_score, evaluate_board
from helpers import explain_illegal_move, finalize_game, finalize_game_if_over, get_game_state, init_game, save_game_state, execute_move

# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

def register_routes(app):

    @app.route("/")
    def home():
        print(f"\n[HOME] Handling GET / request")
        print(f"[HOME] TESTING mode: {app.config.get('TESTING', False)}")
        print(f"[HOME] Session has _test_position_set: {session.get('_test_position_set', False)}")
        print(f"[HOME] Current session keys: {list(session.keys())}")
        
        # Only clear/init session if not in testing mode AND not restoring from test position
        # In testing, preserve session state across page loads
        should_clear = not app.config.get('TESTING', False) and not session.get('_test_position_set')
        
        print(f"[HOME] Should clear session: {should_clear}")
        
        if should_clear:
            session.clear()
            session.modified = True
            init_game()
        # Don't clear flag - preserve test position
        # Flag will be cleared when first move is made
        
        # Get current board state to pass to template
        board, move_history, captured_pieces, special_moves = get_game_state()
        initial_position = board.fen()
        
        print(f"[HOME] Rendering with FEN: {initial_position}")
        
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
        
        return render_template("chess.html", 
                             initial_position=initial_position, 
                             status=status,
                             initial_material=material,
                             initial_evaluation=evaluation,
                             initial_move_history=move_history,
                             initial_captured_pieces=captured_pieces,
                             initial_special_moves=special_moves,
                             initial_turn="white" if board.turn == chess.WHITE else "black",
                             ai_enabled=app.config.get('AI_ENABLED', False))


    @app.route("/move", methods=["POST"])
    def move():
        board, move_history, captured_pieces, special_moves = get_game_state()

        print("\n--- DEBUG: MOVE REQUEST ---")
        print("Session keys:", list(session.keys()))
        print("Current board FEN:", board.fen())
        print("Current turn:", "white" if board.turn == chess.WHITE else "black")

        data = request.get_json()
        from_sq = data.get("from")
        to_sq = data.get("to")
        promotion = data.get("promotion")

        # ✅ ADD THIS: Normalize promotion piece to lowercase (UCI standard)
        if promotion:
            promotion = promotion.lower()

        uci = f"{from_sq}{to_sq}{promotion}" if promotion else f"{from_sq}{to_sq}"
        print("Move received (UCI):", uci)

        try:
            move = chess.Move.from_uci(uci)
            print("Parsed move object:", move)

            if move not in board.legal_moves:
                reason = explain_illegal_move(board, move)
                
                # 🔧 ENHANCED LOGGING FOR ILLEGAL MOVES
                print("ILLEGAL MOVE DETECTED")
                print(f"   From: {from_sq} → To: {to_sq}")
                print(f"   UCI: {uci}")
                print(f"   Reason: {reason}")
                print(f"   Legal moves: {[m.uci() for m in list(board.legal_moves)[:10]]}...")  # Show first 10
                print("--- END DEBUG ---\n")

                return jsonify({
                    "status": "illegal",
                    "message": reason,
                    "material": material_score(board),
                    "evaluation": evaluate_board(board)
                })
            
            print("Move is LEGAL, executing...")
            
            # Execute the move
            execute_move(board, move, move_history, captured_pieces, special_moves)

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
                
            print(f"Board after player move: {board.fen()}")

            # Clear test position flag if it was set (after first move)
            session.pop('_test_position_set', None)
            
            # Save updated session state
            save_game_state(board, move_history, captured_pieces, special_moves)

            material = material_score(board)
            evaluation = evaluate_board(board)

            print(f"\nFinal board state: {board.fen()}")
            print(f"Move history: {move_history}")
            print(f"Game over: {board.is_game_over()}")
            print(f"material score: {material}")
            print(f"evaluation score: {evaluation}")
            print("--- END DEBUG ---\n")

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
                "game_over": board.is_game_over(),
                "move_history": move_history,
                "captured_pieces": captured_pieces,
                "material": material,
                "evaluation": evaluation
            }

            return jsonify(response_data)

        except Exception as e:
            print("\nEXCEPTION IN /move ENDPOINT")
            print(f"   Error: {e}")
            print(f"   Move data: from={from_sq}, to={to_sq}, promotion={promotion}")
            print("--- END DEBUG ---\n")
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
                "game_over": board.is_game_over(),
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
                "material": material_score(board),
                "evaluation": evaluate_board(board)
            })

        print("\nAI MOVE:")
        try:
            ai_move = choose_ai_move(board, depth=2)
            if ai_move is None:
                print("   WARNING: AI returned None, using random move")
                ai_move = random.choice(list(board.legal_moves))
                print(f"   Random move: {ai_move.uci()}")
        except Exception as e:
            print(f"   ERROR in AI: {e}")
            ai_move = random.choice(list(board.legal_moves))
            print(f"   Fallback random move: {ai_move.uci()}")
        
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
            "game_over": board.is_game_over(),
            "move_history": move_history,
            "captured_pieces": captured_pieces,
            "material": material_score(board),
            "evaluation": evaluate_board(board)
        })


    @app.route("/reset", methods=["POST"])
    def reset():
        print("\nRESET GAME")
        game_id = session.get("game_id")
        if game_id:
            game = db.session.get(Game, game_id)
            if game and game.ended_at is None:
                finalize_game(game, "*", "abandoned")
        session.clear()  # This also clears _test_position_set flag
        init_game()
        print("--- END DEBUG ---\n")

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
    
    @app.route("/resign", methods=["POST"])
    def resign():
        game_id = session.get("game_id")
        if not game_id:
            return jsonify({"status": "error", "message": "No active game"}), 400

        game = db.session.get(Game, game_id)
        if not game or game.ended_at:
            return jsonify({"status": "error", "message": "Game already ended"}), 400

        data = request.get_json()
        resigning_color = data.get("color")  # "white" or "black"

        if resigning_color not in ("white", "black"):
            return jsonify({"status": "error", "message": "Invalid color"}), 400

        winner = "black" if resigning_color == "white" else "white"
        result = "1-0" if winner == "white" else "0-1"

        finalize_game(game, result, "resignation")
        db.session.commit()

        return jsonify({
            "status": "ok",
            "result": result,
            "winner": winner,
            "termination_reason": "resignation",
            "game_over": True
        })

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
        
        # Set session state
        session['fen'] = fen
        session['move_history'] = data.get('move_history', [])
        session['captured_pieces'] = data.get('captured_pieces', {'white': [], 'black': []})
        session['special_moves'] = data.get('special_moves', [])
        session['_test_position_set'] = True  # Flag to prevent session.clear() in home route
        session.modified = True  # Force Flask-Session to save changes
        
        print(f"[TEST_SET_POSITION] Session keys after setting: {list(session.keys())}")
        print(f"[TEST_SET_POSITION] Set FEN to: {fen}")
        
        board = chess.Board(fen)
        
        return jsonify({
            "status": "ok",
            "fen": fen,
            "turn": "white" if board.turn == chess.WHITE else "black",
            "check": board.is_check(),
            "checkmate": board.is_checkmate(),
            "stalemate": board.is_stalemate(),
            "game_over": board.is_game_over(),
            "material": material_score(board),
            "evaluation": evaluate_board(board)
        })