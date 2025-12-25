from playwright.sync_api import Page

def setup_board_position(page: Page, fen: str, move_history=None, 
                        captured_pieces=None, special_moves=None):
    """
    Helper to set exact board position using test endpoint
    Call page.goto(live_server) before using this
    """
    payload = {
        "fen": fen,
        "move_history": move_history or [],
        "captured_pieces": captured_pieces or {"white": [], "black": []},
        "special_moves": special_moves or []
    }
    
    # Use page.evaluate to make fetch call
    result = page.evaluate(f"""
        fetch('/test/set_position', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({payload})
        }})
        .then(r => r.json())
    """)
    
    # Reload page to apply new position
    page.reload()
    page.wait_for_selector("#board")
    page.wait_for_timeout(500)
    
    return result

