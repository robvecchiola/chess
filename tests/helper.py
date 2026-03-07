import re

from flask import json
from playwright.sync_api import Page, expect, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urlparse


def wait_for_board_ready(page: Page, timeout: int = 10000):
    """Wait until the chessboard container is visible, sized, and squares are rendered."""
    expect(page.locator("#board")).to_be_visible(timeout=timeout)
    page.wait_for_function(
        """
        () => {
            const board = document.getElementById('board');
            if (!board) return false;
            const rect = board.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) return false;
            return board.querySelectorAll('[data-square]').length >= 64;
        }
        """,
        timeout=timeout,
    )


def _matches_post_path(resp, expected_path: str) -> bool:
    """Match POST responses by exact path (avoid /move matching /ai-move)."""
    if resp.request.method != "POST":
        return False

    parsed_path = urlparse(resp.url).path.rstrip("/") or "/"
    target_path = expected_path.rstrip("/") or "/"
    return parsed_path == target_path


def _wait_for_animation_idle(page: Page, timeout: int = 10000):
    """
    Wait for chessboard.js temporary animation pieces to clear from <body>.

    During board.position() animations, transient piece images are appended to
    body, and dragging in that window is flaky.
    """
    page.wait_for_function(
        """
        () => {
            const bodyPieces = Array.from(document.querySelectorAll("body > img[data-piece]"));
            const visibleBodyPieces = bodyPieces.filter((img) => {
                const style = window.getComputedStyle(img);
                return style.display !== "none" && style.visibility !== "hidden";
            });
            return visibleBodyPieces.length === 0;
        }
        """,
        timeout=timeout,
    )


def _wait_for_human_move_ready(page: Page, from_square: str, timeout: int = 10000):
    """Wait until UI indicates the human side can make a stable drag/drop move."""
    page.wait_for_function(
        """
        (sourceSquare) => {
            const board = window.board;
            if (!board || board.draggable !== true) return false;

            const state = window.CHESS_CONFIG || {};
            if (state.game_over) return false;
            if (state.turn && state.turn !== "white") return false;

            const bodyPieces = Array.from(document.querySelectorAll("body > img[data-piece]"));
            const hasVisibleBodyPiece = bodyPieces.some((img) => {
                const style = window.getComputedStyle(img);
                return style.display !== "none" && style.visibility !== "hidden";
            });
            if (hasVisibleBodyPiece) return false;

            const sourcePiece = document.querySelector(`[data-square="${sourceSquare}"] img`);
            if (!sourcePiece) return false;
            const style = window.getComputedStyle(sourcePiece);
            return style && style.display !== "none" && style.visibility !== "hidden";
        }
        """,
        arg=from_square,
        timeout=timeout,
    )


def assert_turn(page: Page, color: str, timeout: int = 10000):
    """Assert the UI banner shows the expected side to move."""
    expected = "White's turn" if color == "white" else "Black's turn"
    expect(page.locator("#game-status")).to_have_text(re.compile(expected), timeout=timeout)


def setup_board_position(
    page: Page,
    fen: str,
    move_history=None,
    captured_pieces=None,
    special_moves=None,
    live_server: str = "http://localhost:5000",
):
    """
    Set exact board/session state via /test/set_position and synchronize UI state.
    """
    wait_for_board_ready(page)

    payload = {
        "fen": fen,
        "move_history": move_history or [],
        "captured_pieces": captured_pieces or {"white": [], "black": []},
        "special_moves": special_moves or [],
    }

    result = page.evaluate(
        f"""
        async () => {{
            const response = await fetch('/test/set_position', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                credentials: 'include',
                body: JSON.stringify({json.dumps(payload)})
            }});
            return await response.json();
        }}
        """
    )

    print(f"[SETUP] /test/set_position returned: {result}")
    assert result.get("status") == "ok", f"Failed to set position: {result}"

    print("[SETUP] Updating page state from /test/set_position result")
    update_script = f"""
    window.CHESS_CONFIG = window.CHESS_CONFIG || {{}};
    window.CHESS_CONFIG.fen = {json.dumps(result['fen'])};
    window.CHESS_CONFIG.move_history = {json.dumps(result['move_history'])};
    window.CHESS_CONFIG.captured_pieces = {json.dumps(result['captured_pieces'])};
    window.CHESS_CONFIG.special_moves = {json.dumps(result['special_moves'])};
    window.CHESS_CONFIG.special_moves_by_color = {json.dumps(result.get('special_moves_by_color', {'white': [], 'black': []}))};
    window.CHESS_CONFIG.material = {result['material']};
    window.CHESS_CONFIG.evaluation = {result['evaluation']};
    window.CHESS_CONFIG.turn = {json.dumps(result['turn'])};
    window.CHESS_CONFIG.check = {json.dumps(result['check'])};
    window.CHESS_CONFIG.checkmate = {json.dumps(result['checkmate'])};
    window.CHESS_CONFIG.stalemate = {json.dumps(result['stalemate'])};
    window.CHESS_CONFIG.game_over = {json.dumps(result['game_over'])};
    window.CHESS_CONFIG.fifty_moves = {json.dumps(result['fifty_moves'])};
    window.CHESS_CONFIG.can_claim_repetition = {json.dumps(result['can_claim_repetition'])};
    window.CHESS_CONFIG.insufficient_material = {json.dumps(result['insufficient_material'])};
    window.CHESS_CONFIG.termination_reason = {json.dumps(result.get('termination_reason'))};

    if (window.board) {{
        board.position({json.dumps(result['fen'])}, false);
    }}

    if (typeof updateMaterialAdvantage === 'function') {{
        updateMaterialAdvantage(window.CHESS_CONFIG.material);
    }}
    if (typeof updatePositionEvaluation === 'function') {{
        updatePositionEvaluation(window.CHESS_CONFIG.evaluation);
    }}
    if (typeof updateMoveHistory === 'function') {{
        updateMoveHistory(window.CHESS_CONFIG.move_history);
    }} else {{
        const tbody = document.querySelector('#move-history tbody');
        if (tbody) {{
            tbody.innerHTML = '';
            const history = window.CHESS_CONFIG.move_history || [];
            for (let i = 0; i < history.length; i += 2) {{
                const moveNumber = Math.floor(i / 2) + 1;
                const whiteMove = history[i] || '';
                const blackMove = history[i + 1] || '';
                const row = document.createElement('tr');
                row.innerHTML = `<td>${{moveNumber}}</td><td>${{whiteMove}}</td><td>${{blackMove}}</td>`;
                tbody.appendChild(row);
            }}
        }}
    }}
    if (typeof updateCaptured === 'function') {{
        updateCaptured(window.CHESS_CONFIG.captured_pieces);
    }} else {{
        const renderCapturedFallback = (selector, pieces, colorPrefix) => {{
            const container = document.querySelector(selector);
            if (!container) return;
            container.innerHTML = '';
            (pieces || []).forEach(piece => {{
                const code = (typeof piece === 'string' && piece.length === 1)
                    ? colorPrefix + piece.toUpperCase()
                    : piece;
                const img = document.createElement('img');
                img.src = `/static/images/chesspieces/wikipedia/${{code}}.png`;
                img.alt = code;
                img.className = 'captured-piece';
                container.appendChild(img);
            }});
        }};

        renderCapturedFallback('#white-captured', window.CHESS_CONFIG.captured_pieces?.white, 'b');
        renderCapturedFallback('#black-captured', window.CHESS_CONFIG.captured_pieces?.black, 'w');
    }}
    if (typeof updateSpecialMove === 'function') {{
        updateSpecialMove(window.CHESS_CONFIG.special_moves_by_color || window.CHESS_CONFIG.special_moves);
    }}

    const statusElement = document.getElementById('game-status');
    if (statusElement) {{
        let finalStatus;
        if (window.CHESS_CONFIG.game_over) {{
            if (window.CHESS_CONFIG.checkmate) {{
                const winner = window.CHESS_CONFIG.turn === "white" ? "Black" : "White";
                finalStatus = `${{winner}} wins - checkmate`;
            }} else if (window.CHESS_CONFIG.stalemate) {{
                finalStatus = "Draw - stalemate";
            }} else if (window.CHESS_CONFIG.insufficient_material) {{
                finalStatus = "Draw - insufficient material";
            }} else {{
                finalStatus = "Game over";
            }}
        }} else if (window.CHESS_CONFIG.fifty_moves) {{
            finalStatus = "50-move rule available";
        }} else if (window.CHESS_CONFIG.can_claim_repetition) {{
            finalStatus = "Threefold repetition available";
        }} else {{
            finalStatus = window.CHESS_CONFIG.turn === "white" ? "White's turn" : "Black's turn";
            if (window.CHESS_CONFIG.check) {{
                finalStatus += " - Check!";
            }}
        }}
        statusElement.textContent = finalStatus;
    }}

    true;
    """

    try:
        result_confirm = page.evaluate(update_script)
        print(f"[SETUP] Page state update successful (result: {result_confirm})")
    except Exception as e:
        print(f"[SETUP] ERROR: Could not execute state update script: {e}")
        raise AssertionError(f"Failed to update page state: {e}")

    expected_board = fen.split(" ")[0]
    page.wait_for_function(
        """
        (expectedBoardFen) => {
            const fen = window.CHESS_CONFIG?.fen;
            if (!fen) return false;
            return fen.split(' ')[0] === expectedBoardFen;
        }
        """,
        arg=expected_board,
        timeout=5000,
    )
    page.wait_for_function(
        "() => { const el = document.getElementById('game-status'); return !!el && el.textContent.length > 0; }",
        timeout=5000,
    )


def get_piece_in_square(page: Page, square: str):
    """Return locator for the piece image in a square."""
    return page.locator(f'[data-square="{square}"] img')


def send_move(
    page: Page,
    from_square: str,
    to_square: str,
    promotion: str = None,
    timeout: int = 10000,
):
    """Submit a move through sendMove() and wait for /move response."""
    _wait_for_human_move_ready(page, from_square, timeout=timeout)
    with page.expect_response(
        lambda resp: _matches_post_path(resp, "/move"),
        timeout=timeout,
    ) as move_response_info:
        page.evaluate(
            "({fromSq, toSq, promo}) => sendMove(fromSq, toSq, promo)",
            {"fromSq": from_square, "toSq": to_square, "promo": promotion},
        )
    return move_response_info.value.json()


def send_move_and_wait_for_ai(
    page: Page,
    from_square: str,
    to_square: str,
    promotion: str = None,
    move_timeout: int = 10000,
    ai_timeout: int = 15000,
):
    """Submit a legal move and wait for both /move and /ai-move responses."""
    move_result = None
    try:
        with page.expect_response(
            lambda resp: _matches_post_path(resp, "/ai-move"),
            timeout=ai_timeout,
        ) as ai_response_info:
            move_result = send_move(
                page,
                from_square,
                to_square,
                promotion=promotion,
                timeout=move_timeout,
            )
        ai_result = ai_response_info.value.json()
    except PlaywrightTimeoutError as exc:
        status_text = page.locator("#game-status").text_content()
        error_text = page.locator("#error-message").text_content()
        raise AssertionError(
            f"Timed out waiting for /ai-move after {from_square}->{to_square}. "
            f"/move={move_result} | game-status={status_text!r} | error={error_text!r}"
        ) from exc
    _wait_for_ai_cycle_to_settle(page, ai_result, timeout=ai_timeout)
    return move_result, ai_result


def drag_move(page: Page, from_square: str, to_square: str, timeout: int = 10000):
    """Drag a piece and wait for the /move response."""
    _wait_for_human_move_ready(page, from_square, timeout=timeout)
    _wait_for_animation_idle(page, timeout=timeout)

    from_piece = get_piece_in_square(page, from_square)
    to_square_elem = page.locator(f'[data-square="{to_square}"]')
    expect(from_piece.first).to_be_visible(timeout=timeout)
    expect(to_square_elem).to_be_visible(timeout=timeout)

    with page.expect_response(
        lambda resp: _matches_post_path(resp, "/move"),
        timeout=timeout,
    ) as move_response_info:
        from_piece.first.drag_to(to_square_elem)
    return move_response_info.value.json()


def drag_move_and_wait_for_ai(
    page: Page,
    from_square: str,
    to_square: str,
    move_timeout: int = 10000,
    ai_timeout: int = 15000,
):
    """Drag a legal move and wait for both /move and /ai-move responses."""
    move_result = None
    try:
        with page.expect_response(
            lambda resp: _matches_post_path(resp, "/ai-move"),
            timeout=ai_timeout,
        ) as ai_response_info:
            move_result = drag_move(page, from_square, to_square, timeout=move_timeout)
        ai_result = ai_response_info.value.json()
    except PlaywrightTimeoutError as exc:
        status_text = page.locator("#game-status").text_content()
        error_text = page.locator("#error-message").text_content()
        debug_state = page.evaluate(
            """
            () => ({
                fen: window.CHESS_CONFIG?.fen,
                turn: window.CHESS_CONFIG?.turn,
                boardDraggable: window.board?.draggable,
            })
            """
        )
        raise AssertionError(
            f"Timed out waiting for /ai-move after drag {from_square}->{to_square}. "
            f"/move={move_result} | game-status={status_text!r} | error={error_text!r} "
            f"| state={debug_state}"
        ) from exc
    _wait_for_ai_cycle_to_settle(page, ai_result, timeout=ai_timeout)
    return move_result, ai_result


def _wait_for_ai_cycle_to_settle(page: Page, ai_result: dict, timeout: int = 15000):
    """
    Wait for frontend state sync after /ai-move.

    The response can arrive before the JS callback finishes updating local
    flags/UI, so a follow-up move may start too early.
    """
    if ai_result.get("game_over") or ai_result.get("status") == "game_over":
        return

    expected_board_fen = None
    if ai_result.get("fen"):
        expected_board_fen = ai_result["fen"].split(" ")[0]

    page.wait_for_function(
        """
        ({boardFen}) => {
            const board = window.board;
            if (!board || board.draggable !== true) return false;

            const bodyPieces = Array.from(document.querySelectorAll("body > img[data-piece]"));
            const hasVisibleBodyPiece = bodyPieces.some((img) => {
                const style = window.getComputedStyle(img);
                return style.display !== "none" && style.visibility !== "hidden";
            });
            if (hasVisibleBodyPiece) return false;

            if (boardFen) {
                if (typeof board.position !== "function") return false;
                const currentBoardFen = board.position("fen");
                if (!currentBoardFen || currentBoardFen !== boardFen) return false;
            }
            return true;
        }
        """,
        arg={"boardFen": expected_board_fen},
        timeout=timeout,
    )


def drag_piece(page: Page, from_square: str, to_square: str, wait_ms: int = 3000):
    """
    Backward-compatible helper used by older tests.
    """
    from_piece = get_piece_in_square(page, from_square)
    to_square_elem = page.locator(f'[data-square="{to_square}"]')
    from_piece.first.drag_to(to_square_elem)


def make_move(client, from_sq, to_sq, promotion=None):
    payload = {"from": from_sq, "to": to_sq}
    if promotion:
        payload["promotion"] = promotion
    rv = client.post("/move", data=json.dumps(payload), content_type="application/json")
    return rv.get_json()


def set_position(client, fen):
    """Helper to set exact board position using session"""
    with client.session_transaction() as sess:
        sess["fen"] = fen
        sess["move_history"] = []
        sess["captured_pieces"] = {"white": [], "black": []}
        sess["special_moves"] = []
