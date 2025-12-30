from flask import render_template, request, jsonify, session
import chess
import random

from ai import choose_ai_move, material_score
from helpers import explain_illegal_move, get_game_state, init_game, save_game_state

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
            status = "White's turn" if board.turn == chess.WHITE else "Black's turn"
        
        return render_template("chess.html", initial_position=initial_position, status=status)


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
                    "material": material_score(board)
                })
            
            print("Move is LEGAL, executing...")
            
            # Detect special move
            special_move = None
            if board.is_castling(move):
                special_move = "Castling"
                print("   Special: Castling")
            elif board.is_en_passant(move):
                special_move = "En Passant"
                print("   Special: En Passant")
            elif promotion:
                special_move = f"Promotion to {promotion.upper()}"
                print(f"   Special: Promotion to {promotion.upper()}")
            
            # SAN before push
            move_san = board.san(move)
            print(f"   SAN notation: {move_san}")

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
                    print(f"   Player captured: {captured_piece.symbol()}")

            board.push(move)
            move_history.append(move_san)

            if special_move:
                special_moves.append(special_move)

            print(f"Board after player move: {board.fen()}")

            # -----------------------------------------------------------
            # AI Move
            # -----------------------------------------------------------
            if app.config.get("AI_ENABLED", True) and not board.is_game_over():
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
                
                ai_special_move = None
                if board.is_castling(ai_move):
                    ai_special_move = "Castling"
                    print("   AI Special: Castling")
                elif board.is_en_passant(ai_move):
                    ai_special_move = "En Passant"
                    print("   AI Special: En Passant")
                
                ai_san = board.san(ai_move)
                print(f"   AI SAN: {ai_san}")

                if board.is_capture(ai_move):
                    if board.is_en_passant(ai_move):
                        captured_piece = chess.Piece(chess.PAWN, not board.turn)
                    else:
                        captured_piece = board.piece_at(ai_move.to_square)

                    if captured_piece:
                        # Store by capturing player: white piece captured → black captured it
                        color_key = "black" if captured_piece.color == chess.WHITE else "white"
                        captured_pieces[color_key].append(captured_piece.symbol())
                        print(f"   AI captured: {captured_piece.symbol()}")
                
                # --- FORCE AI PROMOTION SAFETY NET ---
                if (
                    board.piece_at(ai_move.from_square)
                    and board.piece_at(ai_move.from_square).piece_type == chess.PAWN
                    and chess.square_rank(ai_move.to_square) in (0, 7)
                    and ai_move.promotion is None
                ):
                    ai_move = chess.Move(
                        ai_move.from_square,
                        ai_move.to_square,
                        promotion=chess.QUEEN
                    )
                    ai_special_move = "Promotion to Q"

                board.push(ai_move)
                move_history.append(ai_san)
                if ai_special_move:
                    special_moves.append(ai_special_move)

            # Clear test position flag if it was set (after first move)
            session.pop('_test_position_set', None)
            
            # Save updated session state
            save_game_state(board, move_history, captured_pieces, special_moves)

            material = material_score(board)

            print(f"\nFinal board state: {board.fen()}")
            print(f"Move history: {move_history}")
            print(f"Game over: {board.is_game_over()}")
            print(f"material score: {material}")
            print("--- END DEBUG ---\n")

            return jsonify({
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
                "material": material
            })

        except Exception as e:
            print("\nEXCEPTION IN /move ENDPOINT")
            print(f"   Error: {e}")
            print(f"   Move data: from={from_sq}, to={to_sq}, promotion={promotion}")
            print("--- END DEBUG ---\n")
            return jsonify({"status": "illegal", "message": str(e), "material": material_score(board)})


    @app.route("/reset", methods=["POST"])
    def reset():
        print("\nRESET GAME")
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
            "material": 0
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
            "material":0
        })