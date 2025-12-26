from flask import json
from playwright.sync_api import Page

def setup_board_position(page: Page, fen: str, move_history=None, 
                        captured_pieces=None, special_moves=None):
    """
    Helper to set exact board position using test endpoint.
    
    Flow:
    1. Call /test/set_position endpoint to store FEN, move_history, etc in session
    2. Set _test_position_set flag to prevent home route from clearing session  
    3. Reload page to render new board state
    4. Home route respects the flag and preserves the test position
    
    Call page.goto(live_server) before using this.
    
    NOTE: Uses generic img selector instead of dynamic .piece-XXXXX class
    because chessboard.js generates piece classes with hash suffixes that
    change on each board initialization.
    """
    payload = {
        "fen": fen,
        "move_history": move_history or [],
        "captured_pieces": captured_pieces or {"white": [], "black": []},
        "special_moves": special_moves or []
    }
    
    # Set position in session via test endpoint
    # This also sets the _test_position_set flag
    page.evaluate(f"""
        fetch('/test/set_position', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({payload})
        }})
        .then(r => r.json())
    """)
    
    # Wait for endpoint to process
    page.wait_for_timeout(300)
    
    # Reload page - home route will preserve our test position due to flag
    page.reload()
    page.wait_for_selector("#board")
    # Extra wait to ensure Chessboard.js fully re-initializes with new pieces
    page.wait_for_timeout(3000)

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