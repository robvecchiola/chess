from flask import json
from playwright.sync_api import Page
from pathlib import Path
import os
import time

def setup_board_position(page: Page, fen: str, move_history=None, 
                        captured_pieces=None, special_moves=None, live_server: str = "http://localhost:5000"):
    """
    Helper to set exact board position using test endpoint.
    CRITICAL: Tests that use this MUST clear cookies BEFORE page.goto()!
    
    Recommended pattern:
        page.context.clear_cookies()  # STEP 1: Clear old cookies
        page.goto(live_server)        # STEP 2: Load page with clean session
        setup_board_position(page, fen, ...)  # STEP 3: Override session state
    
    Uses browser's fetch with credentials to ensure Flask-Session cookie
    is sent and maintained across the /test/set_position call.
    """
    # 🔑 Delete Flask-Session files to ensure fresh session
    session_dir = Path("flask_session")
    if session_dir.exists():
        for session_file in session_dir.glob("*"):
            if session_file.is_file():
                try:
                    session_file.unlink()
                except Exception:
                    pass  # Ignore errors, continue
    
    payload = {
        "fen": fen,
        "move_history": move_history or [],
        "captured_pieces": captured_pieces or {"white": [], "black": []},
        "special_moves": special_moves or []
    }
    
    # Use browser's fetch with credentials: 'include' to send session cookies
    result = page.evaluate(f"""
        async () => {{
            const response = await fetch('/test/set_position', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                credentials: 'include',
                body: JSON.stringify({json.dumps(payload)})
            }});
            const data = await response.json();
            console.log('SET_POSITION RESULT:', data);
            
            // Get current cookies
            const cookies = document.cookie;
            console.log('Current cookies:', cookies);
            
            return data;
        }}
    """)
    
    print(f"[SETUP] /test/set_position returned: {result}")
    assert result.get('status') == 'ok', f"Failed to set position: {result}"
    
    # Extra delay to ensure session is written to disk
    page.wait_for_timeout(2000)
    
    # 🔑 CRITICAL: Update the window.CHESS_CONFIG in-place WITHOUT navigating the page
    # This avoids creating a second session that would override our /test/set_position changes
    # We just update the JavaScript variables that chessboard-init.js uses
    
    print(f"[SETUP] Updating page state from /test/set_position result")
    
    # Update the window.CHESS_CONFIG object with the result from /test/set_position
    # This makes chessboard-init.js see the updated state without page reload
    update_script = f"""
    // Update window.CHESS_CONFIG with the new state from /test/set_position
    window.CHESS_CONFIG = window.CHESS_CONFIG || {{}};
    window.CHESS_CONFIG.fen = {json.dumps(result['fen'])};
    window.CHESS_CONFIG.move_history = {json.dumps(result['move_history'])};
    window.CHESS_CONFIG.captured_pieces = {json.dumps(result['captured_pieces'])};
    window.CHESS_CONFIG.special_moves = {json.dumps(result['special_moves'])};
    window.CHESS_CONFIG.material = {result['material']};
    window.CHESS_CONFIG.evaluation = {result['evaluation']};
    window.CHESS_CONFIG.turn = {json.dumps(result['turn'])};
    window.CHESS_CONFIG.check = {json.dumps(result['check'])};
    window.CHESS_CONFIG.checkmate = {json.dumps(result['checkmate'])};
    window.CHESS_CONFIG.stalemate = {json.dumps(result['stalemate'])};
    window.CHESS_CONFIG.game_over = {json.dumps(result['game_over'])};
    
    // Now manually call the update functions that chessboard-init.js would call on page load
    // First, reinit the chessboard with the new FEN
    if (window.board) {{
        board.position({json.dumps(result['fen'])}, false);  // false = don't animate
    }}
    
    // Update material display - pass the material VALUE not the whole config
    if (typeof updateMaterialAdvantage === 'function') {{
        updateMaterialAdvantage(window.CHESS_CONFIG.material);
    }}
    
    // Update evaluation display - pass the evaluation VALUE and use correct function name
    if (typeof updatePositionEvaluation === 'function') {{
        updatePositionEvaluation(window.CHESS_CONFIG.evaluation);
    }}
    
    // Update status - pass the full config object
    if (typeof updateStatus === 'function') {{
        updateStatus(window.CHESS_CONFIG);
    }}
    
    // Update move history display
    if (typeof updateMoveHistory === 'function') {{
        updateMoveHistory(window.CHESS_CONFIG.move_history);
    }}
    
    // Update captured pieces display - use correct function name
    if (typeof updateCaptured === 'function') {{
        updateCaptured(window.CHESS_CONFIG.captured_pieces);
    }}
    
    // Update special moves display - use correct function name
    if (typeof updateSpecialMove === 'function') {{
        updateSpecialMove(window.CHESS_CONFIG.special_moves);
    }}
    
    true;  // Return value to confirm script executed
    """
    
    try:
        result_confirm = page.evaluate(update_script)
        print(f"[SETUP] Page state update successful (result: {result_confirm})")
    except Exception as e:
        print(f"[SETUP] ERROR: Could not execute state update script: {e}")
        raise AssertionError(f"Failed to update page state: {e}")
    
    # Wait for any DOM updates to finish
    page.wait_for_timeout(500)
    
    # 🔍 DEBUG: Check what the page has NOW
    config_fen = page.evaluate("window.CHESS_CONFIG?.fen")
    config_material = page.evaluate("window.CHESS_CONFIG?.material")
    print(f"[SETUP] After state update - CHESS_CONFIG.fen = {config_fen}")
    print(f"[SETUP] After state update - CHESS_CONFIG.material = {config_material}")
    
    # 🔑 VERIFY: The state was updated correctly
    # Note: Castling rights may be modified by the chess engine, so we only check the board position part
    fen_board_only = fen.split(' ')[0]  # Just the position part, ignore castling/ep/etc
    config_fen_board_only = config_fen.split(' ')[0] if config_fen else ""
    
    if config_fen_board_only != fen_board_only:
        print(f"[SETUP] ERROR: Page has wrong board position! Expected {fen_board_only}, got {config_fen_board_only}")
        print(f"[SETUP]        (Complete FEN: expected {fen}, got {config_fen})")
        raise AssertionError(f"Session not loaded correctly - page has wrong FEN: {config_fen} instead of {fen}")
    
    # Verify status element exists and has been updated
    try:
        page.wait_for_function(
            "() => { const el = document.getElementById('game-status'); return el && el.textContent.length > 0; }",
            timeout=5000
        )
    except Exception as e:
        print(f"[SETUP] Warning: Status element update timeout: {e}")

def get_piece_in_square(page: Page, square: str):
    """
    Get the img element for a piece in a specific square
    Chessboard.js renders pieces as img tags inside square divs.
    
    Args:
        page: Playwright Page object
        square: Square name like "e2", "a1", etc.
    
    Returns:
        Locator for img tag in that square (piece might be absent)
    """
    return page.locator(f'[data-square="{square}"] img')

def drag_piece(page: Page, from_square: str, to_square: str, wait_ms: int = 3000):
    """
    Helper to drag a piece from one square to another
    Handles the dynamic nature of chessboard.js piece classes
    
    Args:
        page: Playwright Page object
        from_square: Source square like "e2"
        to_square: Target square like "e4"
        wait_ms: Wait time after drag (ms) for server response
    """
    from_piece = get_piece_in_square(page, from_square)
    to_square_elem = page.locator(f'[data-square="{to_square}"]')
    from_piece.drag_to(to_square_elem)
    page.wait_for_timeout(wait_ms)

def make_move(client, from_sq, to_sq, promotion=None):
    payload = {"from": from_sq, "to": to_sq}
    if promotion:
        payload["promotion"] = promotion
    rv = client.post("/move", data=json.dumps(payload), content_type="application/json")
    return rv.get_json()

def set_position(client, fen):
    """Helper to set exact board position using session"""
    with client.session_transaction() as sess:
        sess['fen'] = fen
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []