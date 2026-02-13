# Flask Chess AI ♟️

A fully-featured web-based chess application built with Flask, featuring an AI opponent powered by minimax algorithm with alpha-beta pruning.

## Features

- **Complete Chess Rules Implementation**
  - All piece movements (pawns, knights, bishops, rooks, queens, kings)
  - Special moves: castling (kingside & queenside), en passant, pawn promotion
  - Check, checkmate, and stalemate detection
  - Draw conditions: threefold repetition, fifty-move rule, insufficient material

- **AI Opponent**
  - Minimax algorithm with alpha-beta pruning (configurable depth)
  - Position evaluation with material advantage scoring
  - Automatic move selection for black pieces

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
rm -rf /home/casualchess/mysite/chess/venv


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
- `DevelopmentConfig` - Debug mode enabled, fixed secret key
- `TestingConfig` - For test suite (in-memory sessions)
- `ProductionConfig` - Production settings (requires environment variables)

**Environment Variables:**
- `SECRET_KEY` - Required for production (session encryption)

## Testing

### Run All Tests
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
- Flask-Session configured with `SESSION_PERMANENT = True` for test suite
- Sessions persist across page navigations via filesystem storage
- E2E tests use `page.context.clear_cookies()` at test start for isolation
- Each test gets fresh cookies while maintaining session integrity

**AI Configuration**:
- Unit/Integration tests: `AI_ENABLED = False` (isolates player moves)
- E2E tests: `AI_ENABLED = True` (tests AI behavior)
- Always configure AI for test scope

See [TESTING_GUIDE.md](TESTING_GUIDE.md) for comprehensive testing documentation.

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

- Session state uses FEN notation for board persistence
- Move history rebuilt from SAN moves for repetition detection
- AI defaults to depth=2 for performance (configurable in routes.py)
- Promotion dialog appears automatically for pawn reaching rank 8
- Turn enforcement prevents dragging opponent pieces

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