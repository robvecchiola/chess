from flask import json
from playwright.sync_api import Page

def setup_board_position(page: Page, fen: str, move_history=None, 
                        captured_pieces=None, special_moves=None):
    """
    Helper to set exact board position using test endpoint.
    
    Uses browser's fetch with credentials to ensure Flask-Session cookie
    is sent and maintained across the /test/set_position call.
    
    Note: With function-scoped browser context (from conftest.py),
    each test gets a fresh browser context, so no stale session cookies.
    """
    # Clear any cookies from previous tests to ensure fresh session
    page.context.clear_cookies()
    
    payload = {
        "fen": fen,
        "move_history": move_history or [],
        "captured_pieces": captured_pieces or {"white": [], "black": []},
        "special_moves": special_moves or []
    }
    
    # Use browser's fetch with credentials: 'include' to send session cookies
    # This is critical - without credentials, fetch won't send the session cookie!
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
    
    # Extra delay to ensure session is written to disk AND browser receives Set-Cookie
    page.wait_for_timeout(3000)
    
    # Navigate to the page (instead of reload) to force a fresh GET with the session cookie
    # This ensures Flask loads the updated session from disk
    print(f"[SETUP] Navigating to / to load session with FEN: {fen}")
    page.goto(page.url.split('?')[0])  # Navigate to /, stripping any query params
    page.wait_for_load_state('networkidle')
    
    # Wait for board to stabilize after navigation
    page.wait_for_timeout(1000)

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