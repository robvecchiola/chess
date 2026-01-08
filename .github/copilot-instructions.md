# Chess Game - AI Coding Agent Instructions

## Architecture Overview

This is a Flask-based web chess application with a random AI opponent. The architecture follows a clean separation:

- **Backend (Python/Flask)**: [app.py](../app.py), [routes.py](../routes.py), [helpers.py](../helpers.py), [config.py](../config.py)
- **Frontend (jQuery + chessboard.js)**: [static/js/chessboard-init.js](../static/js/chessboard-init.js), [templates/chess.html](../templates/chess.html)
- **State management**: Server-side Flask sessions stored in filesystem ([flask_session/](../flask_session/))
- **Chess logic**: python-chess library (not chess library - see requirements.txt)

## Critical Session State Pattern

Game state is persisted in Flask sessions via three helpers in [helpers.py](../helpers.py):
- `init_game()` - Creates new game with starting FEN, empty move history, empty captured pieces, empty special moves
- `get_game_state()` - Retrieves `(board, move_history, captured_pieces, special_moves)` from session
- `save_game_state(board, move_history, captured_pieces, special_moves)` - Persists state back to session

**Always call `save_game_state()` after modifying board state.** Missing this causes desynchronization between client and server.

The board state is stored in FEN format in the session, and move_history is maintained separately for display purposes. The board is not rebuilt from move_history to avoid SAN parsing issues.

## Move Flow (Client → Server → AI)

1. Frontend sends UCI move via POST `/move` (e.g., `{"from": "e2", "to": "e4", "promotion": "q"}`)
2. Backend validates using `python-chess` library's `legal_moves`
3. Player move executed: `board.push(move)`
4. AI immediately responds with `random.choice(list(board.legal_moves))` if `AI_ENABLED=True`
5. Both moves tracked in SAN notation via `board.san(move)` before push
6. Captured pieces tracked separately for display (handles en passant edge case)
7. Special moves (castling, en passant, promotion) tracked for display
8. Updated state returned: FEN, turn, game flags, move_history, captured_pieces, special_moves

## JavaScript Frontend Patterns

[chessboard-init.js](../static/js/chessboard-init.js) implements:

- **Snapshot-rollback pattern**: `lastPosition` captured in `onDragStart`, restored on illegal moves via `rollbackPosition()`
- **Promotion handling**: Detects pawn reaching rank 8, disables dragging, shows modal, sends promotion piece to server
- **Turn enforcement**: Blocks dragging opponent's pieces by checking `currentTurn` and piece color
- **AJAX move flow**: Disables dragging during server communication, re-enables on response

## Configuration

[config.py](../config.py) uses class-based configs:
- `BaseConfig` - Shared settings (SECRET_KEY from env or auto-generated, Flask-Session filesystem storage)
- `DevelopmentConfig(BaseConfig)` - Current active config in [app.py](../app.py)
- `ProductionConfig(BaseConfig)` - Placeholder for prod settings

**Flask-Session must be initialized AFTER setting `app.secret_key` but BEFORE registering routes** (see [app.py](../app.py) initialization order).

## Testing Structure

Three test files in [tests/](../tests/):
- [test_chess_logic.py](../tests/test_chess_logic.py) - Pure python-chess validation (legal moves, captures, promotion, en passant)
- [test_routes_api.py](../tests/test_routes_api.py) - Flask API tests with `AI_ENABLED=False` to isolate player moves
- [test_ai_and_endgames.py](../tests/test_ai_and_endgames.py) - AI behavior and game-over detection with `AI_ENABLED=True`

**Always disable AI in tests unless specifically testing AI** via `app.config['AI_ENABLED'] = False` in fixtures.

Helper pattern for API tests:
```python
def make_move(client, from_sq, to_sq, promotion=None):
    payload = {"from": from_sq, "to": to_sq}
    if promotion: payload["promotion"] = promotion
    return client.post("/move", data=json.dumps(payload), 
                      content_type="application/json").get_json()
```

## Development Commands

```bash
# Setup venv (Windows)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
flask run
# Or: python app.py

# Run tests
pytest
pytest tests/test_chess_logic.py -v
```

## Common Patterns to Follow

1. **UCI notation for moves**: All moves use UCI (e.g., "e2e4", "e7e8q" for promotion)
2. **SAN for display**: Convert to SAN via `board.san(move)` before pushing for move history
3. **Capture detection**: Check `board.is_capture(move)` and handle `board.is_en_passant(move)` separately
4. **Emoji comments**: Codebase uses emoji markers (🔑, 🗄️) for important config notes
5. **Debug logging**: Routes use print statements for debugging (see [routes.py](../routes.py) move function)
