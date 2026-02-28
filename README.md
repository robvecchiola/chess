# Flask Chess AI ♟️

A fully-featured web-based chess application built with Flask, featuring an AI opponent powered by minimax algorithm with alpha-beta pruning.

## Features

- **Complete Chess Rules Implementation**
  - All piece movements (pawns, knights, bishops, rooks, queens, kings)
  - Special moves: castling (kingside & queenside), en passant, pawn promotion
  - Check, checkmate, and stalemate detection
  - Draw conditions: threefold repetition, fifty-move rule, insufficient material

- **AI Opponent**
  - Minimax search with alpha-beta pruning and quiescence search for capture/check stabilization
  - Move ordering (promotions, captures first) and tie-breaking heuristics
  - Evaluation uses material values and positional piece-square tables
  - Server-side selection prefers top-N moves and filters moves that leave high-value pieces hanging

- **User Interface**
  - Interactive drag-and-drop chessboard (chessboard.js)
  - Real-time game status updates
  - Move history with algebraic notation (SAN)
  - Captured pieces display
  - Material advantage indicator
  - Special moves tracking

- **Game Management**
  - Server-side game state persistence (Flask-Session)
  - Move validation with detailed error messages
  - New game reset functionality

## Technologies

- **Backend**: Flask, python-chess
- **Frontend**: jQuery, chessboard.js
- **Session Management**: Flask-Session (filesystem storage)
- **Testing**: pytest (100+ tests with E2E coverage)
- **AI**: Custom minimax implementation with evaluation function

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/robvecchiola/chess.git
cd chess
```

### 2. Set Up Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
deactivate  # To exit virtual environment
```
rm -rf /home/casualchess/.virtualenvs/venv


### 3. Install Dependencies
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Running the Application

### Development Server
```bash
flask run
```
Or:
python app.py
```

The application will be available at `http://127.0.0.1:5000`

### Configuration

Edit `config.py` to customize settings:
### Configuration

Edit `config.py` to customize settings:
- `DevelopmentConfig` — local dev settings
- `TestingConfig` — used by tests (enables test-only endpoints)
- `ProductionConfig` — production settings (use env vars)

Environment variables to consider:
- `SECRET_KEY` — required in production

## Testing

### Run All Tests
```bash
pytest -v
```

### Testing

Run the full test suite:

```bash
pytest -v
```
### Run Specific Test Files
```bash
pytest tests/test_chess_logic.py -v        # Chess engine tests
pytest tests/test_routes_api.py -v         # API endpoint tests
pytest tests/test_ai_and_endgames.py -v    # AI behavior tests
pytest tests/test_e2e_playwright.py -v     # E2E browser tests
```

### Test Coverage
- **Chess Logic**: Legal moves, captures, special moves, pins, checks
- **API Routes**: Move validation, session management, game state
- **AI & Endgames**: AI move selection, checkmate, stalemate, draws
- **E2E/Browser**: User interactions, UI updates, game flow

### Testing Architecture

**Session Persistence in Tests**:
Testing notes (summary)

- The AI implementation is in `ai.py` (minimax + quiescence). The server selects AI moves via `choose_ai_move()`; the UI and the `/ai-move` route use a shallow depth by default to keep responsiveness — depth is configurable in code.
- Integration tests should set `app.config['AI_ENABLED'] = False` unless the test is explicitly exercising AI behavior.
- The test-only endpoint `/test/set_position` is only enabled when `app.config['TESTING']` is True.

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for detailed testing patterns and E2E notes.

## Project Structure

```
chess/
├── app.py                 # Flask application entry point
├── routes.py              # Route handlers and move logic
├── helpers.py             # Session management and game state
├── ai.py                  # AI move selection (minimax)
├── config.py              # Configuration classes
├── constants.py           # Piece values and constants
├── static/
│   ├── css/              # Stylesheets
│   ├── js/               # Frontend JavaScript (chessboard-init.js)
│   └── images/           # Chess piece images
├── templates/
│   └── chess.html        # Main game template
├── tests/                # Pytest test suite
│   ├── test_chess_logic.py
│   ├── test_routes_api.py
│   └── test_ai_and_endgames.py
└── flask_session/        # Session storage directory
```

## API Endpoints

- `GET /` - Main game page
- `POST /move` - Submit a move (player + AI response)
- `POST /reset` - Start a new game
- `POST /test/set_position` - Set custom board position (testing only)

## Game Flow

1. **Player Move**: Frontend sends UCI move (e.g., `{"from": "e2", "to": "e4"}`)
2. **Validation**: Backend validates move using python-chess
3. **AI Response**: AI immediately calculates and executes best move
4. **State Update**: Session stores FEN, move history, captured pieces
5. **Response**: JSON with updated board state, game flags, material advantage

## Development Notes

## Development notes

- Session state uses FEN notation for board persistence.
- Move history is stored in session and SAN is used for repetition detection.
- AI: see `ai.py` — the engine uses minimax with alpha-beta pruning, quiescence search, move ordering, and evaluation combining material and piece-square tables. The server-side `/ai-move` route calls `choose_ai_move(board, depth=1)`; callers may supply different depths for stronger play.
- Promotion dialog appears automatically for pawn reaching rank 8.
- Turn enforcement prevents dragging opponent pieces in the UI.

## Known Limitations

- AI uses minimax (not neural network) - may not play at grandmaster level
- No opening book or endgame tablebase
- Session cleanup requires manual flask_session/ directory management

## Contributing

Pull requests welcome! Please ensure all tests pass:
```bash
pytest -v
```

## License

MIT License - see LICENSE file for details

## Author

**rob** - [robvecchiola](https://github.com/robvecchiola)

---

### Quick Reference

**Update Dependencies:**
```bash
pip freeze > requirements.txt
```

**Install from requirements:**
```bash
pip install -r requirements.txt
```

**Run with Debug:**
```bash
flask run --debug
```

**make db changes:**
```bash
flask db migrate -m "blah"
```

**run the db upgrade:**
```bash
flask db upgrade
```

used this to create virtual dr in pythonanywhere:
mkvirtualenv venv --python=python3.11
/home/casualchess/.virtualenvs/venv

manually add libraries to requirements/dev.in then run:
```bash
pip-compile requirements-dev.in