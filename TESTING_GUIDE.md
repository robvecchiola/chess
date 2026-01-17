# Chess Application Testing Guide

Comprehensive guide for writing unit, integration, and E2E tests for this Flask chess application.

---

## Table of Contents

1. [Testing Architecture](#testing-architecture)
2. [Common Pitfalls & Solutions](#common-pitfalls--solutions)
3. [Unit Testing](#unit-testing)
4. [Integration Testing](#integration-testing)
5. [E2E Testing with Playwright](#e2e-testing-with-playwright)
6. [Session Testing](#session-testing)
7. [Test Patterns & Best Practices](#test-patterns--best-practices)
8. [Debugging Failed Tests](#debugging-failed-tests)

---

## Testing Architecture

### Test Structure
```
tests/
├── test_chess_logic.py          # Pure python-chess validation
├── test_routes_api.py            # Flask API tests (AI disabled)
├── test_ai_and_endgames.py       # AI behavior & game-over detection
├── test_session_persistence.py   # Session/state management
├── test_castling_edge_cases.py   # Castling rules
├── test_promotion_edge_cases.py  # Pawn promotion scenarios
├── e2e/                          # Playwright browser tests
└── helper.py                     # Shared test utilities
```

### Test Layers

| Layer | Scope | Tools | AI Enabled? |
|-------|-------|-------|-------------|
| **Unit** | Pure chess logic | `python-chess`, `pytest` | N/A |
| **Integration** | Flask routes + logic | `pytest`, `Flask test client` | No (unless testing AI) |
| **E2E** | Full browser interaction | `Playwright`, `pytest-playwright` | Yes (unless specified) |

---

## Session Management & Test Isolation

### 🔑 Critical: Cookie Clearing for Test Isolation

**Problem**: E2E tests share Flask-Session cookies, causing session contamination.

**Solution**: Clear cookies at test start via `setup_board_position()` helper:

```python
def setup_board_position(page: Page, fen: str, ...):
    """Set exact board position - handles session isolation."""
    # CRITICAL: Clear cookies from previous test
    page.context.clear_cookies()
    
    # Now set position with fresh session
    result = page.evaluate(f"""
        fetch('/test/set_position', {{
            method: 'POST',
            credentials: 'include',  # Send fresh session cookies
            body: JSON.stringify({payload})
        }})
    """)
    
    page.wait_for_timeout(3000)  # Wait for disk write
    page.goto("/")               # Load with fresh session
```

**Why It Works**:
1. `clear_cookies()` removes stale session IDs
2. Fresh POST creates new session file on disk
3. Browser receives Set-Cookie response
4. `page.goto()` loads page with correct session
5. **Result**: Each test is truly isolated

### 🗄️ Flask-Session Configuration Requirements

**Critical Settings** (in [config.py](config.py) `TestingConfigFilesystem`):

```python
SESSION_PERMANENT = True           # Must be True for tests
SESSION_TYPE = 'filesystem'        # Use disk storage
SESSION_FILE_DIR = './flask_session'
SESSION_USE_SIGNER = True
```

**Why Each Setting Matters**:
- `SESSION_PERMANENT = True`: Sessions survive page reloads (essential for E2E)
- `SESSION_TYPE = 'filesystem'`: Sessions persist on disk between requests
- `SESSION_FILE_DIR`: Centralized location for test session files
- `SESSION_USE_SIGNER`: Sign cookies to prevent tampering

**What Breaks Without These**:
- `SESSION_PERMANENT = False`: Sessions cleared on page reload → position lost
- `SESSION_TYPE = 'default'`: In-memory sessions cleared between requests
- Missing signer: Cookie validation fails

## Common Pitfalls & Solutions

### ❌ Pitfall #1: Illegal Pawn Moves

**Problem:**
```python
# WRONG: Pawns can't capture straight ahead
make_move(client, "e7", "e8", promotion="q")  # If e8 has a piece

# WRONG: Pawns can't move backwards
make_move(client, "h2", "h1", promotion="r")
```

**Solution:**
```python
# RIGHT: Pawns must capture diagonally
make_move(client, "e7", "d8", promotion="q")  # Capture diagonally

# RIGHT: Move forward to promote
set_position(client, '4k3/7P/8/8/8/8/8/4K3 w - - 0 1')
make_move(client, "h7", "h8", promotion="q")
```

### ❌ Pitfall #2: Session State Corruption with `set_position()`

**Problem:**
```python
# Using set_position() can create mismatches between FEN and move_history
set_position(client, 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
make_move(client, "e1", "g1")  # May fail due to session issues
```

**Solution:**
```python
# Option 1: Use reset_board() + natural moves (PREFERRED)
reset_board(client)
moves = [("e2", "e4"), ("e7", "e5"), ("g1", "f3"), ("g8", "f6")]
for from_sq, to_sq in moves:
    make_move(client, from_sq, to_sq)

# Option 2: If using set_position(), understand it's for isolated tests
# Don't mix set_position() with move sequences
```

### ❌ Pitfall #3: Incorrect FEN Notation

**Problem:**
```python
# WRONG: Using file letter as rank number
fen = f'8/{file.upper()}7/8/8/8/8/8/K7 w - - 0 1'  # 'A' becomes rank '8'

# WRONG: Not collapsing empty squares
fen = '11111111/8/8/8/8/8/8/8 w KQkq - 0 1'  # Should be '8/8/...'
```

**Solution:**
```python
# RIGHT: Proper FEN construction
def build_rank_fen(piece_positions):
    """
    piece_positions: dict like {0: 'P', 3: 'K'} where key is file index (0-7)
    """
    rank = ['1'] * 8
    for file_idx, piece in piece_positions.items():
        rank[file_idx] = piece
    
    # Collapse consecutive numbers
    fen = ''.join(rank)
    fen = fen.replace('11111111', '8')
    fen = fen.replace('1111', '4')
    fen = fen.replace('111', '3')
    fen = fen.replace('11', '2')
    return fen

# Example: Pawn on a7
rank7_fen = build_rank_fen({0: 'P'})  # "P7"
fen = f'8/{rank7_fen}/8/8/8/8/8/4K2k w - - 0 1'
```

### ❌ Pitfall #4: Forgetting Chess Rules in Test Expectations

**Problem:**
```python
# Expecting no check after queen promotion adjacent to king
set_position(client, 'r6k/1P6/8/8/8/8/8/K7 w - - 0 1')
rv = make_move(client, "b7", "a8", promotion="q")
assert not board.is_check()  # WRONG: Queen on a8 checks king on h8!
```

**Solution:**
```python
# Account for actual chess rules
rv = make_move(client, "b7", "a8", promotion="q")
board = chess.Board(rv["fen"])
assert board.is_check()  # Queen gives check along rank
```

### ❌ Pitfall #5: AI_ENABLED in Wrong Tests

**Problem:**
```python
def test_player_move(client):
    # AI makes automatic response, doubling moves
    app.config['AI_ENABLED'] = True  # WRONG for testing player moves
    rv = make_move(client, "e2", "e4")
    assert len(rv["move_history"]) == 1  # FAILS: AI added move
```

**Solution:**
```python
def test_player_move(client):
    app.config['AI_ENABLED'] = False  # Disable AI for player-only tests
    rv = make_move(client, "e2", "e4")
    assert len(rv["move_history"]) == 1  # PASS
```

### ❌ Pitfall #6: Session Contamination Between E2E Tests

**Problem:**
```python
# Test 1: Sets promotion position
def test_promotion(page, base_url):
    setup_board_position(page, 'promotion_fen')
    # ...plays moves...

# Test 2: Expects castling position
def test_castling(page, base_url):
    setup_board_position(page, 'castling_fen')
    # But page.goto("/") loads STARTING FEN instead!
    # ❌ FAILS: Session has old FEN or wrong session ID
```

**Solution** (in helper):
```python
def setup_board_position(page: Page, fen: str, ...):
    # MUST clear cookies at start of each test
    page.context.clear_cookies()  # ← Remove stale session cookies
    
    # Now set position with fresh session
    result = page.evaluate(f"...fetch('/test/set_position'...)...")
    page.wait_for_timeout(3000)  # Wait for disk write
    page.goto("/")               # Load with fresh session
    # ✅ WORKS: Fresh session, correct FEN
```

**Why This Matters**:
- Session-scoped browser context (shared cookies) = each test inherits previous test's session ID
- If previous test called `/reset`, session file deleted but cookie still points to it
- Next test's `/test/set_position` creates NEW session file
- But browser cookie still has OLD session ID
- `page.goto("/")` looks for OLD session file, loads STARTING_FEN
- Result: Wrong FEN, test fails
- Solution: Clear cookies, get fresh session ID each time

### ❌ Pitfall #6: Castling Rights After Moves

**Problem:**
```python
# Expecting queenside castling after king moved
set_position(client, 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
rv = make_move(client, "e1", "g1")  # King castles kingside

# Later test expects white to still have Q rights
assert "Q" in rv["fen"].split()[2]  # FAILS: King moved, loses BOTH rights
```

**Solution:**
```python
# Castling moves the king → loses BOTH castling rights
rv = make_move(client, "e1", "g1")
castling_rights = rv["fen"].split()[2]
assert "K" not in castling_rights  # King moved
assert "Q" not in castling_rights  # King moved (both sides gone)
assert "kq" in castling_rights     # Black retains rights
```

---

## Unit Testing

### Testing Pure Chess Logic

**File:** `test_chess_logic.py`

Tests `python-chess` library behavior directly - no Flask, no routes.

```python
import chess
import pytest

@pytest.fixture
def new_board():
    """Return a fresh chess board."""
    return chess.Board()

def test_legal_move(new_board):
    """Test that e2e4 is legal from starting position"""
    move = chess.Move.from_uci("e2e4")
    assert move in new_board.legal_moves
    
    new_board.push(move)
    assert new_board.piece_at(chess.E4).symbol() == "P"

def test_illegal_move(new_board):
    """Test that pawns can't move 3 squares"""
    move = chess.Move.from_uci("e2e5")
    assert move not in new_board.legal_moves

def test_en_passant():
    """Test en passant detection"""
    board = chess.Board()
    board.set_fen("8/8/8/1pP5/8/8/8/8 w - b6 0 1")
    
    move = chess.Move.from_uci("c5b6")
    assert move in board.legal_moves
    assert board.is_en_passant(move)
```

**Key Patterns:**
- ✅ Test one concept per test
- ✅ Use `chess.Board()` directly
- ✅ Test illegal moves, not just legal ones
- ✅ Cover edge cases (en passant, castling, promotion)

---

## Integration Testing

### Testing Flask Routes with Game Logic

**File:** `test_routes_api.py`

Tests API endpoints with `AI_ENABLED = False` to isolate player moves.

```python
import pytest
import json
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['AI_ENABLED'] = False  # ← Critical!
    with app.test_client() as client:
        yield client

def make_move(client, from_sq, to_sq, promotion=None):
    """Helper to make API move request"""
    payload = {"from": from_sq, "to": to_sq}
    if promotion:
        payload["promotion"] = promotion
    
    rv = client.post("/move", 
                     data=json.dumps(payload),
                     content_type="application/json")
    return rv.get_json()

def reset_board(client):
    """Reset game state"""
    client.post("/reset")

def test_legal_move(client):
    reset_board(client)
    rv = make_move(client, "e2", "e4")
    
    assert rv["status"] == "ok"
    assert rv["turn"] == "black"
    assert len(rv["move_history"]) == 1

def test_castling_kingside(client):
    reset_board(client)
    
    # Clear path for castling
    moves = [
        ("e2", "e4"), ("e7", "e5"),
        ("g1", "f3"), ("g8", "f6"),
        ("f1", "e2"), ("f8", "e7"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    # Castle kingside
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "ok"
    assert "Castling" in rv["special_moves"]
```

**Critical Setup:**
```python
# ALWAYS in integration fixtures:
app.config['TESTING'] = True       # Use in-memory session
app.config['AI_ENABLED'] = False   # Disable AI auto-response
```

---

## E2E Testing with Playwright

### Browser-Based Tests

**File:** `tests/test_e2e_playwright.py`

**Critical Setup Pattern**:
```python
import pytest
from playwright.sync_api import Page, expect
from tests.helper import setup_board_position, reset_board

def test_player_makes_move(page: Page, base_url):
    """Test dragging a piece makes a move"""
    page.goto(base_url)
    
    # Wait for board to load
    expect(page.locator("#board")).to_be_visible()
    
    # Drag white pawn e2 → e4
    page.drag_and_drop(
        '[data-square="e2"]',
        '[data-square="e4"]'
    )
    
    # Verify move appeared in history
    move_history = page.locator("#move-history tbody")
    expect(move_history).to_contain_text("e4")

def test_promotion_with_setup(page: Page, base_url):
    """Test promotion dialog with isolated session"""
    # ✅ Use helper for proper session isolation
    setup_board_position(
        page, 
        '1nbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1'
    )
    
    # Verify correct position loaded
    board_content = page.content()
    assert 'wP' in board_content  # White pawn on a7
    
    # Drag pawn to promotion square
    page.drag_and_drop('[data-square="a7"]', '[data-square="a8"]')
    
    # Promotion dialog should appear
    expect(page.locator("#promotion-dialog")).to_be_visible()
    
    # Select queen
    page.locator("button[data-piece='q']").click()
    
    # Verify promotion occurred
    special_moves = page.locator("#special-white li")
    expect(special_moves).to_contain_text("Promotion")
```

**Session-Aware Helper** (in `tests/helper.py`):
```python
from playwright.sync_api import Page
import json

def setup_board_position(page: Page, fen: str, move_history=None, 
                        captured_pieces=None, special_moves=None):
    """
    Set exact board position with proper session isolation.
    
    🔑 KEY: Clears cookies to ensure fresh session per test.
    """
    # CRITICAL: Clear cookies from previous test
    page.context.clear_cookies()
    
    payload = {
        "fen": fen,
        "move_history": move_history or [],
        "captured_pieces": captured_pieces or {"white": [], "black": []},
        "special_moves": special_moves or []
    }
    
    # Use fetch with credentials to send session cookies
    result = page.evaluate(f"""
        async () => {{
            const response = await fetch('/test/set_position', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                credentials: 'include',  # ← Critical for session
                body: JSON.stringify({json.dumps(payload)})
            }});
            return await response.json();
        }}
    """)
    
    assert result.get('status') == 'ok'
    
    # Wait for Flask-Session to write to disk
    page.wait_for_timeout(3000)
    
    # Navigate (not reload) to force fresh GET request
    page.goto("/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)  # Extra time for DOM updates
```

**Setup** (in `tests/conftest.py`):
```python
import pytest
from threading import Thread
import time

@pytest.fixture(scope="session")
def flask_app():
    """Create app for entire test session."""
    from app import create_app
    from config import TestingConfigFilesystem
    from extensions import db
    
    app = create_app(TestingConfigFilesystem)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture(scope="session")
def base_url(flask_app):
    """Start Flask server and return base URL."""
    def run_app():
        flask_app.run(port=5000, debug=False, use_reloader=False)
    
    thread = Thread(target=run_app, daemon=True)
    thread.start()
    time.sleep(2)  # Wait for server startup
    
    return "http://localhost:5000"

# Playwright fixtures are auto-provided by pytest-playwright
# page, browser, base_url, etc.
```

---

## Session Testing

### API Session Persistence

**File:** `test_routes_api.py`

Integration tests validate Flask session behavior:

```python
def test_session_persists_across_requests(client):
    """Session state persists between API calls"""
    reset_board(client)
    
    rv1 = make_move(client, "e2", "e4")
    assert len(rv1["move_history"]) == 1
    
    rv2 = make_move(client, "e7", "e5")
    assert len(rv2["move_history"]) == 2  # Includes both moves

def test_session_isolated_between_clients(client):
    """Two clients have separate sessions"""
    reset_board(client)
    make_move(client, "e2", "e4")
    
    # New client starts fresh
    with app.test_client() as client2:
        rv = make_move(client2, "e2", "e4")
        assert len(rv["move_history"]) == 1  # Not 2

def test_session_survives_illegal_move(client):
    """Illegal move doesn't corrupt session"""
    reset_board(client)
    make_move(client, "e2", "e4")
    
    # Try illegal move
    rv_illegal = make_move(client, "e4", "e6")
    assert rv_illegal["status"] == "illegal"
    
    # Session still valid
    rv_legal = make_move(client, "e7", "e5")
    assert rv_legal["status"] == "ok"
    assert len(rv_legal["move_history"]) == 2
```

### E2E Session Isolation

**Critical**: E2E tests must clear cookies at start to prevent session contamination:

```python
def test_promotion_then_castling(page: Page, base_url):
    """Two consecutive tests with different positions."""
    # Test 1: Promotion
    setup_board_position(page, promotion_fen)  # Clears cookies internally
    # ...test promotion...
    
    # Test 2: Castling (separate test in real usage)
    def test_castling(page: Page, base_url):
        setup_board_position(page, castling_fen)  # ← Clears cookies
        # setup_board_position() calls page.context.clear_cookies()
        # This ensures fresh session, not contaminated by test 1
```

**Why Separate Tests**:
- pytest creates new `page` fixture for each test
- But if tests manually reuse page, must call `setup_board_position()`
- Cookie clearing in helper prevents session ID mismatches

---

## Test Patterns & Best Practices

### Pattern 1: Reset Before Each Test

```python
def test_something(client):
    reset_board(client)  # ← Always start fresh
    # ... test code
```

### Pattern 2: Test Both Success and Failure

```python
def test_castling_legal_and_illegal(client):
    # Test legal castling
    # ... setup moves
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "ok"
    
    # Test illegal castling (king already moved)
    rv = make_move(client, "e8", "g8")  # Try to castle again
    assert rv["status"] == "illegal"
```

### Pattern 3: Verify Response Structure

```python
def test_move_response_structure(client):
    reset_board(client)
    rv = make_move(client, "e2", "e4")
    
    # Verify all expected fields
    assert "status" in rv
    assert "fen" in rv
    assert "turn" in rv
    assert "move_history" in rv
    assert "captured_pieces" in rv
    assert "game_over" in rv
```

### Pattern 4: Use FEN for Complex Setups

**API Tests:**
```python
from tests.helper import set_position

def test_specific_position(client):
    # Don't play 20 moves - set position directly
    set_position(client, 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
    
    # Now test from this position
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "ok"
```

**E2E Tests:**
```python
from tests.helper import setup_board_position

def test_castling_position(page: Page, base_url):
    # ✅ Helper handles session isolation
    setup_board_position(
        page, 
        'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1'
    )
    
    # Page is loaded with correct FEN, fresh session
    page.drag_and_drop('[data-square="e1"]', '[data-square="g1"]')
    expect(page.locator("#special-white li")).to_contain_text("Castling")
```

### Pattern 5: Test Isolation (Critical for E2E)

**Good - Each test independent:**
```python
# API Tests
def test_move_A(client):
    reset_board(client)  # Fresh session
    rv = make_move(client, "e2", "e4")
    assert rv["status"] == "ok"

def test_move_B(client):
    reset_board(client)  # Fresh session
    rv = make_move(client, "e2", "e4")
    assert rv["status"] == "ok"

# E2E Tests
def test_e2e_move_A(page: Page, base_url):
    page.goto(base_url)  # Fresh page
    page.drag_and_drop('[data-square="e2"]', '[data-square="e4"]')

def test_e2e_move_B(page: Page, base_url):
    page.goto(base_url)  # Fresh page (pytest creates new fixture)
    page.drag_and_drop('[data-square="e2"]', '[data-square="e4"]')

# E2E with setup
def test_e2e_promotion(page: Page, base_url):
    setup_board_position(page, promotion_fen)  # Clears cookies, sets position
    page.drag_and_drop('[data-square="a7"]', '[data-square="a8"]')

def test_e2e_castling(page: Page, base_url):
    setup_board_position(page, castling_fen)  # Fresh session, no contamination
    page.drag_and_drop('[data-square="e1"]', '[data-square="g1"]')
```

**Bad - Tests depend on each other:**
```python
# ❌ DON'T DO THIS
def test_move_A(client):
    make_move(client, "e2", "e4")

def test_move_B(client):
    # Assumes e4 was already played!
    make_move(client, "e7", "e5")

# ❌ DON'T DO THIS (E2E)
def test_e2e_setup(page: Page, base_url):
    page.goto(base_url)
    page.evaluate("globalState = 'promotion_ready'")  # Modifies page state

def test_e2e_test_with_setup(page: Page, base_url):
    # Assumes globalState was set by previous test!
    # FAILS: Fresh page fixture = clean globalState
```

---

## Debugging Failed Tests

### Step 1: Check Debug Output

Tests print detailed debug info:
```
--- DEBUG: MOVE REQUEST ---
Session keys: ['fen', 'move_history', ...]
Current board FEN: rnbqkbnr/pppppppp/...
Current turn: white
Move received (UCI): e2e5
ILLEGAL MOVE DETECTED
   From: e2 → To: e5
   UCI: e2e5
   Reason: Pawns can only move 1-2 squares forward.
```

### Step 2: Verify FEN is Correct

```python
# Add debugging to test
def test_something(client):
    set_position(client, 'YOUR_FEN_HERE')
    
    # Print actual board state
    with client.session_transaction() as sess:
        print(f"Actual FEN: {sess['fen']}")
    
    board = chess.Board(sess['fen'])
    print(f"Legal moves: {[m.uci() for m in board.legal_moves]}")
```

### Step 3: Check Turn Order

```python
# Common issue: trying to move wrong color
rv = make_move(client, "e2", "e4")  # White
rv = make_move(client, "d2", "d4")  # ERROR: Still white's turn!
```

### Step 4: Validate Move is Actually Legal

```python
import chess

# Manually verify move
board = chess.Board('YOUR_FEN')
move = chess.Move.from_uci("e2e4")
print(f"Is legal: {move in board.legal_moves}")
print(f"All legal moves: {[m.uci() for m in board.legal_moves]}")
```

---

## Quick Reference

### Common Test Commands

```bash
# Run all tests
pytest

# Run specific file
pytest tests/test_routes_api.py

# Run specific test
pytest tests/test_routes_api.py::test_legal_move

# Run with verbose output
pytest -v

# Run with print statements visible
pytest -s

# Run only failed tests from last run
pytest --lf

# Run E2E tests
pytest tests/e2e/ --headed  # Show browser
```

### Test File Templates

**Unit Test Template:**
```python
import chess
import pytest

@pytest.fixture
def board():
    return chess.Board()

def test_something(board):
    # Test pure chess logic
    assert True
```

**Integration Test Template:**
```python
import pytest
from app import app
from tests.test_routes_api import make_move, reset_board

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['AI_ENABLED'] = False
    with app.test_client() as client:
        yield client

def test_something(client):
    reset_board(client)
    rv = make_move(client, "e2", "e4")
    assert rv["status"] == "ok"
```

**E2E Test Template:**
```python
import pytest
from playwright.sync_api import Page, expect

def test_something(page: Page, base_url):
    page.goto(base_url)
    expect(page.locator("#board")).to_be_visible()
    # Test browser interaction
```

---

## Checklist for New Tests

- [ ] Test file follows naming convention (`test_*.py`)
- [ ] Fixture sets `AI_ENABLED` appropriately
- [ ] Each test calls `reset_board()` or `set_position()`
- [ ] Test is independent (doesn't rely on other tests)
- [ ] Both success AND failure cases tested
- [ ] Response structure validated
- [ ] FEN positions are valid chess positions
- [ ] Move sequences follow turn order (white, black, white...)
- [ ] Expected behavior matches actual chess rules
- [ ] Test has docstring explaining what it tests

---

## Common Test Scenarios

### Scenario: Testing Checkmate

```python
def test_fools_mate(client):
    reset_board(client)
    
    moves = [("f2","f3"), ("e7","e5"), ("g2","g4"), ("d8","h4")]
    for from_sq, to_sq in moves:
        rv = make_move(client, from_sq, to_sq)
    
    assert rv["checkmate"] == True
    assert rv["game_over"] == True
    assert "Black wins" in rv["message"] or "#" in rv["move_history"][-1]
```

### Scenario: Testing En Passant

```python
def test_en_passant(client):
    reset_board(client)
    
    make_move(client, "e2", "e4")
    make_move(client, "a7", "a6")  # Random move
    make_move(client, "e4", "e5")
    make_move(client, "d7", "d5")  # Creates en passant opportunity
    
    rv = make_move(client, "e5", "d6")  # En passant capture
    assert rv["status"] == "ok"
    assert "En Passant" in rv["special_moves"]
```

### Scenario: Testing Promotion

```python
def test_promotion_to_queen(client):
    set_position(client, '1nbqkbnr/P6p/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1')
    
    rv = make_move(client, "a7", "a8", promotion="q")
    
    assert rv["status"] == "ok"
    assert "Promotion" in rv["special_moves"]
    
    board = chess.Board(rv["fen"])
    assert board.piece_at(chess.A8).symbol().upper() == "Q"
```

---

## Troubleshooting Guide

| Error | Likely Cause | Solution |
|-------|--------------|----------|
| `KeyError: 'move_history'` | Illegal move (response doesn't include all fields) | Check move is actually legal; verify FEN setup |
| `AssertionError: assert 'illegal' == 'ok'` | Move is not legal in position | Verify piece is on from_square, path is clear, turn is correct |
| `"It's X's turn — you can't move opponent's pieces"` | Wrong turn order | Check alternating white/black moves |
| `"Pawns can't capture straight ahead"` | Trying to promote with occupied square | Use diagonal capture or clear square |
| `"There's no piece on that square"` | From square is empty | Verify FEN has piece on from_square |
| `"You can't castle right now"` | Castling rights lost or path blocked | Check king/rook haven't moved, path is clear, not in check |
| Session state mismatch | Using `set_position()` incorrectly | Use `reset_board()` + moves, or ensure FEN is valid |

---

## Summary

1. **Unit tests** = Pure `python-chess` logic, no Flask
2. **Integration tests** = Flask routes + logic, `AI_ENABLED=False`
3. **E2E tests** = Full browser with Playwright
4. **Session tests** = Verify state persistence

**Golden Rules:**
- Always `reset_board()` or `set_position()` at test start
- Disable AI unless specifically testing AI
- Verify move is legal before asserting success
- Test both success and failure cases
- Use helpers like `make_move()` and `set_position()`
- Follow chess rules in test expectations (turn order, piece movement, castling rights)

Happy testing! 🎯
