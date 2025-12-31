from flask import json
from playwright.sync_api import Page

def setup_board_position(page: Page, fen: str, move_history=None, 
                        captured_pieces=None, special_moves=None):
    """
    Helper to set exact board position using test endpoint.
    
    CRITICAL: Uses page.request.post() to access Set-Cookie headers, then manually
    updates browser context cookies AND makes browser re-request the page to sync cookies.
    
    Flow:
    1. page.request.post() to /test/set_position (Playwright API - has headers)
    2. Extract Set-Cookie header from response
    3. Add cookie to browser context via page.context.add_cookies()
    4. Reload page so browser picks up the new cookie
    5. Update board UI via JavaScript
    
    Note: page.reload() is safe here because home() route preserves session when TESTING=True
    """
    payload = {
        "fen": fen,
        "move_history": move_history or [],
        "captured_pieces": captured_pieces or {"white": [], "black": []},
        "special_moves": special_moves or []
    }
    
    # Get base URL
    base_url = page.url.split('/')[0] + '//' + page.url.split('/')[2]
    
    # Use Playwright API request to access response headers
    response = page.request.post(
        f'{base_url}/test/set_position',
        data=payload
    )
    
    response_json = response.json()
    assert response_json.get('status') == 'ok', f"Failed to set position: {response_json}"
    
    # Extract and update session cookie
    set_cookie_header = response.headers.get('set-cookie')
    if set_cookie_header:
        # Parse: "chess_session=<value>; Path=/; HttpOnly; SameSite=Lax"
        cookie_parts = set_cookie_header.split(';')[0]
        name, value = cookie_parts.split('=', 1)
        
        from urllib.parse import urlparse
        parsed = urlparse(page.url)
        
        # Update browser context cookie
        page.context.add_cookies([{
            'name': name.strip(),
            'value': value.strip(),
            'domain': parsed.hostname or 'localhost',
            'path': '/'
            # Note: Don't set httpOnly/sameSite - let browser use defaults
        }])
    
    # Reload page to sync cookie between browser and server
    # This is safe because home() route won't clear session in TESTING mode
    page.reload()
    page.wait_for_load_state('networkidle')
    
    # Update board UI with custom position
    page.evaluate(
        """
        (data) => {
            if (window.board && data.fen) {
                window.board.position(data.fen);
            }
            
            let status = '';
            if (data.checkmate) {
                const winner = data.turn === 'white' ? 'Black' : 'White';
                status = winner + ' wins — Checkmate!';
            } else if (data.stalemate) {
                status = 'Draw';
            } else {
                status = data.turn === 'white' ? "White's turn" : "Black's turn";
                if (data.check) status += ' - Check!';
            }
            
            const statusEl = document.getElementById('game-status');
            if (statusEl) statusEl.textContent = status;
        }
        """,
        response_json
    )
    
    # Wait for board to stabilize
    page.wait_for_timeout(500)

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