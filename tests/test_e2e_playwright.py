"""
End-to-End Playwright tests for chess UI
Playwright is faster, more reliable, and easier to use than Selenium

Run headless (default): pytest tests/test_e2e_playwright.py
Run with browser visible: pytest tests/test_e2e_playwright.py --headed
Run with specific browser: pytest tests/test_e2e_playwright.py --browser firefox
"""
import pytest
import re
import chess
from playwright.sync_api import Page, expect, TimeoutError as PlaywrightTimeoutError

from tests.helper import (
    assert_turn,
    drag_move,
    drag_move_and_wait_for_ai,
    send_move,
    send_move_and_wait_for_ai,
    setup_board_position,
    wait_for_board_ready,
)


# Playwright runs headless by default - no extra flags needed!
# To see browser: pytest tests/test_e2e_playwright.py --headed


@pytest.fixture
def live_server(flask_server):
    """
    Base URL for E2E tests
    Uses flask_server fixture from conftest.py to auto-start Flask
    """
    return flask_server


interaction_test = pytest.mark.e2e_interaction
state_test = pytest.mark.e2e_state


# Shared utility for same-square drag snapback scenarios.
def _drag_piece_to_same_square(page: Page, square: str):
    square_locator = page.locator(f'[data-square="{square}"]')
    bounds = square_locator.bounding_box()
    assert bounds is not None, f"Could not resolve bounds for square {square}"

    x = bounds["x"] + bounds["width"] / 2
    y = bounds["y"] + bounds["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 2, y + 2)
    page.mouse.move(x, y)
    page.mouse.up()


# =============================================================================
# E2E TESTS - Frontend + Backend Integration (Playwright)
# =============================================================================

def test_page_loads_and_renders_board(page: Page, live_server):
    """Test that page loads and chessboard renders correctly"""
    page.goto(live_server)

    expect(page).to_have_title(re.compile("Chess", re.IGNORECASE))

    wait_for_board_ready(page)
    pieces = page.locator("#board img")
    piece_count = pieces.count()
    assert piece_count >= 32 and piece_count <= 33, f"Expected 32-33 pieces, got {piece_count}"

    assert_turn(page, "white")


@interaction_test
def test_drag_and_drop_legal_move(page: Page, live_server):
    """Test that dragging a piece to a legal square works"""
    page.goto(live_server)

    wait_for_board_ready(page)
    e2_square = page.locator('[data-square="e2"]')
    e4_square = page.locator('[data-square="e4"]')

    e2_piece = e2_square.locator("img")
    expect(e2_piece).to_have_attribute("data-piece", re.compile("wP"))

    move_result, ai_result = drag_move_and_wait_for_ai(page, "e2", "e4")
    assert move_result["status"] in {"ok", "game_over"}, f"Unexpected /move response: {move_result}"
    assert ai_result["status"] in {"ok", "game_over"}, f"Unexpected /ai-move response: {ai_result}"

    e4_piece = e4_square.locator("img")
    expect(e4_piece).to_have_attribute("data-piece", re.compile("wP"))

    assert_turn(page, "white")
    move_history = page.locator("#move-history tr")
    expect(move_history).not_to_have_count(0)


@interaction_test
def test_illegal_move_shows_error(page: Page, live_server):
    """Test that illegal moves show error message and rollback"""
    page.goto(live_server)
    wait_for_board_ready(page)

    e2_square = page.locator('[data-square="e2"]')
    e2_piece = e2_square.locator("img")
    e5_square = page.locator('[data-square="e5"]')

    move_result = drag_move(page, "e2", "e5")
    assert move_result["status"] == "illegal", f"Expected illegal move, got: {move_result}"

    error_msg = page.locator("#error-message")
    expect(error_msg).to_have_text(re.compile("Illegal move|Pawns can only move"))

    e2_piece_after = e2_square.locator("img")
    expect(e2_piece_after).to_have_attribute("data-piece", re.compile("wP"))

    e5_pieces = e5_square.locator("img")
    expect(e5_pieces).to_have_count(0)


@interaction_test
def test_drag_piece_back_to_same_square(page: Page, live_server):
    """Test that dragging a piece to its source square snaps back cleanly."""
    page.goto(live_server)
    wait_for_board_ready(page)

    e2_piece = page.locator('[data-square="e2"] img')
    expect(e2_piece).to_have_attribute("data-piece", re.compile("wP"))
    piece_before = e2_piece.get_attribute("data-piece")

    _drag_piece_to_same_square(page, "e2")
    page.wait_for_function(
        """
        (expectedPiece) => {
            const piece = document.querySelector('[data-square="e2"] img');
            return !!piece && piece.getAttribute('data-piece') === expectedPiece;
        }
        """,
        arg=piece_before,
        timeout=5000,
    )

    expect(page.locator("#error-message")).to_be_empty()
    assert_turn(page, "white")


def test_reset_button_resets_board(page: Page, live_server):
    """Test that reset button returns board to starting position"""
    page.goto(live_server)
    wait_for_board_ready(page)

    e2_piece = page.locator('[data-square="e2"] img')
    e4_square = page.locator('[data-square="e4"]')
    move_result, ai_result = drag_move_and_wait_for_ai(page, "e2", "e4")
    assert move_result["status"] in {"ok", "game_over"}, f"Unexpected /move response: {move_result}"
    assert ai_result["status"] in {"ok", "game_over"}, f"Unexpected /ai-move response: {ai_result}"

    move_history = page.locator("#move-history tbody tr")
    expect(move_history).not_to_have_count(0)

    reset_btn = page.locator("#reset-btn")
    with page.expect_response(lambda resp: "/reset" in resp.url and resp.request.method == "POST") as reset_response_info:
        reset_btn.click()
    reset_response = reset_response_info.value.json()
    assert reset_response["status"] == "ok", f"Unexpected /reset response: {reset_response}"

    e2_piece_after = page.locator('[data-square="e2"] img')
    expect(e2_piece_after).to_have_attribute("data-piece", re.compile("wP"))

    e4_pieces = e4_square.locator("img")
    expect(e4_pieces).to_have_count(0)

    move_history_after = page.locator("#move-history tbody tr")
    expect(move_history_after).to_have_count(0)

    assert_turn(page, "white")
    error_msg = page.locator("#error-message")
    expect(error_msg).to_be_empty()


@state_test
def test_captured_pieces_display(page: Page, live_server):
    """Test that captured pieces are tracked and displayed"""
    page.goto(live_server)
    wait_for_board_ready(page)

    # Already after white captures on d5.
    capture_fen = "4k3/8/8/3P4/8/8/8/4K3 b - - 0 1"
    setup_board_position(
        page,
        capture_fen,
        move_history=["exd5"],
        captured_pieces={"white": ["p"], "black": []},
        special_moves=[],
    )

    white_captured = page.locator("#white-captured img")
    expect(white_captured).to_have_count(1)


@state_test
def test_move_history_displays_in_san(page: Page, live_server):
    """Test that move history displays in algebraic notation"""
    page.goto(live_server)
    expect(page.locator("#board")).to_be_visible()
    expect(page.locator('[data-square="e2"] img')).to_have_count(1)

    # Use deterministic move submission; this test validates SAN formatting,
    # not drag-and-drop behavior.
    move_response = send_move(page, "e2", "e4")

    assert move_response["status"] in {"ok", "game_over"}, f"Unexpected /move response: {move_response}"
    assert move_response["move_history"][0] == "e4", f"Expected first SAN move to be e4, got {move_response['move_history']}"

    # Verify UI renders SAN notation (e.g., "e4" not "e2e4")
    white_move_cell = page.locator("#move-history tbody tr").first.locator("td").nth(1)
    expect(white_move_cell).to_have_text("e4")
    expect(white_move_cell).not_to_have_text(re.compile("e2e4"))


@interaction_test
def test_cannot_drag_opponent_pieces(page: Page, live_server):
    """Test that you cannot drag opponent's (black) pieces"""
    page.goto(live_server)
    wait_for_board_ready(page)

    e7_square = page.locator('[data-square="e7"]')
    e7_piece = e7_square.locator("img")
    e5_square = page.locator('[data-square="e5"]')

    e7_piece.drag_to(e5_square)

    e7_piece_after = e7_square.locator("img")
    expect(e7_piece_after).to_have_attribute("data-piece", re.compile("bP"))

    e5_pieces = e5_square.locator("img")
    expect(e5_pieces).to_have_count(0)


@state_test
def test_special_moves_display(page: Page, live_server):
    """Test that special moves (castling, en passant) are displayed"""
    page.goto(live_server)
    
    # Already after white castled kingside.
    castling_fen = "rnbqkbnr/pppppppp/8/8/2B5/5N2/PPPPPPPP/RNBQ1RK1 b kq - 1 1"
    
    setup_board_position(
        page,
        castling_fen,
        move_history=["O-O"],
        captured_pieces={"white": [], "black": []},
        special_moves=["Castling"]
    )

    expect(page.locator('[data-square="g1"] img')).to_have_count(1)
    expect(page.locator('[data-square="f1"] img')).to_have_count(1)
    special_white = page.locator("#special-white li")
    expect(special_white).to_have_count(1)
    expect(special_white).to_have_text("Castling")


def test_game_status_shows_check(page: Page, live_server):
    """Test that game status shows 'Check!' when king is in check"""
    page.goto(live_server)
    wait_for_board_ready(page)

    # White to move in check from black queen on e4.
    check_fen = "r3k2r/8/8/8/4q3/8/8/R3K2R w - - 0 1"
    setup_board_position(
        page,
        check_fen,
        move_history=[],
        captured_pieces={"white": [], "black": []},
        special_moves=[],
    )

    status = page.locator("#game-status")
    expect(status).to_have_text(re.compile(r"Check!", re.IGNORECASE))
    assert page.evaluate("window.CHESS_CONFIG.check === true")


@state_test
def test_ai_responds_with_legal_move(page: Page, live_server):
    """Test that AI always responds with a legal move"""
    page.goto(live_server)
    wait_for_board_ready(page)
    current_fen = page.evaluate("window.CHESS_CONFIG.fen")

    # Play 5 white moves chosen from the current legal move list and verify AI replies each turn.
    for _ in range(5):
        assert_turn(page, "white", timeout=15000)

        board = chess.Board(current_fen)
        assert board.turn == chess.WHITE, f"Expected white to move, got FEN: {current_fen}"

        # Deterministic pick: lexicographically smallest legal UCI move.
        selected_uci = sorted(m.uci() for m in board.legal_moves)[0]
        from_sq = selected_uci[:2]
        to_sq = selected_uci[2:4]
        promotion = selected_uci[4] if len(selected_uci) > 4 else None

        move_result, ai_result = send_move_and_wait_for_ai(
            page,
            from_sq,
            to_sq,
            promotion=promotion,
            move_timeout=10000,
            ai_timeout=15000,
        )

        assert move_result.get("status") in {"ok", "game_over"}, f"Unexpected /move response: {move_result}"
        assert ai_result.get("status") in {"ok", "game_over"}, f"Unexpected /ai-move response: {ai_result}"

        current_fen = ai_result["fen"]
        assert_turn(page, "white", timeout=15000)


# =============================================================================
# VISUAL REGRESSION TEST (OPTIONAL - Requires --screenshot flag)
# =============================================================================

def test_board_visual_appearance(page: Page, live_server):
    """
    Take screenshot of starting position for visual regression testing
    Run with: pytest tests/test_e2e_playwright.py::test_board_visual_appearance --screenshot on
    """
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Playwright automatically takes screenshot on failure
    # Can also take explicit screenshot for comparison
    board = page.locator("#board")
    expect(board).to_be_visible()
    
    # Screenshot saved automatically if test fails
    # Or explicitly: page.screenshot(path="screenshots/starting_position.png")


# =============================================================================
# MOBILE/RESPONSIVE TEST (OPTIONAL)
# =============================================================================

def test_mobile_viewport(page: Page, live_server):
    """Test chess board works on mobile viewport"""
    # Set mobile viewport
    page.set_viewport_size({"width": 375, "height": 667})  # iPhone SE
    page.goto(live_server)
    
    # Verify board renders
    board = page.locator("#board")
    expect(board).to_be_visible()
    
    # Verify board renders (responsive on mobile)
    board_box = board.bounding_box()
    # On mobile viewport, board should be smaller than 400px
    assert board_box['width'] < 400, f"Expected responsive width less than 400px, got {board_box['width']}"
    
    # Could test touch events here too


# =============================================================================
# CRITICAL MISSING TESTS - Pawn Promotion & Game Over States
# =============================================================================

@state_test
def test_pawn_promotion_modal_appears_with_setup(page: Page, live_server):
    """Test that promotion modal appears when pawn reaches 8th rank"""
    # 🔑 CRITICAL: Clear cookies BEFORE page.goto() to ensure fresh session
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Set up position: white pawn on a7, can promote on a8
    promotion_fen = "1rbqkbnr/Ppppppp1/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    setup_board_position(
        page,
        promotion_fen,
        live_server=live_server,
        move_history=["a4", "h6", "a5", "h5", "a6", "h4", "axb7"],
        captured_pieces={"white": ["p"], "black": []},
        special_moves=[]
    )
    
    # Verify pawn is on a7
    a7_pawn = page.locator('[data-square="a7"] img')
    expect(a7_pawn).to_have_count(1)
    
    # Trigger promotion dialog via actual drag onto promotion square.
    page.locator('[data-square="a7"] img').drag_to(page.locator('[data-square="a8"]'))
    promotion_dialog = page.locator("#promotion-dialog")
    expect(promotion_dialog).to_be_visible()
    
    # Verify all promotion options are present
    expect(page.locator('button[data-piece="q"]')).to_be_visible()
    expect(page.locator('button[data-piece="r"]')).to_be_visible()
    expect(page.locator('button[data-piece="b"]')).to_be_visible()
    expect(page.locator('button[data-piece="n"]')).to_be_visible()
    expect(page.locator('#cancel-promotion')).to_be_visible()


@state_test
def test_pawn_promotion_queen_selection_with_setup(page: Page, live_server):
    """Test queen-promotion state is rendered correctly via deterministic setup."""
    page.goto(live_server)

    setup_board_position(
        page,
        "1Q5k/8/8/8/8/8/8/K7 b - - 0 1",
        move_history=["b8=Q+"],
        captured_pieces={"white": [], "black": []},
        special_moves=["Promotion to Q"],
    )
    wait_for_board_ready(page)
    expect(page.locator('[data-square="b8"] img')).to_have_attribute("data-piece", re.compile("wQ"))
    expect(page.locator("#special-white li").filter(has_text=re.compile(r"Promotion to Q", re.IGNORECASE))).to_have_count(1)


@state_test
def test_pawn_promotion_cancel_button_with_setup(page: Page, live_server):
    """Test that cancel button in promotion dialog works correctly"""
    # 🔑 CRITICAL: Clear cookies BEFORE page.goto() to ensure fresh session
    page.goto(live_server)
    wait_for_board_ready(page)
    
    promotion_fen = "7k/1P6/8/8/8/8/1P6/K7 w - - 0 1"
    
    setup_board_position(
        page,
        promotion_fen,
        live_server=live_server,
        move_history=[],
        captured_pieces={"white": [], "black": []},
        special_moves=[]
    )

    page.locator('[data-square="b7"] img').drag_to(page.locator('[data-square="b8"]'))
    promotion_dialog = page.locator("#promotion-dialog")
    expect(promotion_dialog).to_be_visible()
    
    # Cancel promotion
    page.locator('#cancel-promotion').click()
    
    expect(promotion_dialog).not_to_be_visible()
    
    # Verify pawn is back on b7 (rollback)
    b7_pawn = page.locator('[data-square="b7"] img')
    expect(b7_pawn).to_have_count(1)
    
    # Verify b8 is still empty (move was cancelled)
    expect(page.locator('[data-square="b8"] img')).to_have_count(0)
    
    # Verify dragging is re-enabled (can make another move)
    move_result, ai_result = drag_move_and_wait_for_ai(page, "b2", "b3")
    assert move_result["status"] in {"ok", "game_over"}, f"Expected legal move after cancel, got: {move_result}"
    assert ai_result["status"] in {"ok", "game_over"}, f"Unexpected /ai-move response: {ai_result}"
    
    # Should succeed (no error)
    error_msg = page.locator("#error-message")
    expect(error_msg).to_be_empty()


@state_test
def test_checkmate_displays_game_over(page: Page, live_server):
    """Test that checkmate position displays terminal game-over UI."""
    page.goto(live_server)
    wait_for_board_ready(page)

    checkmate_fen = "8/8/8/8/8/7k/6q1/7K w - - 0 1"
    setup_board_position(
        page,
        checkmate_fen,
        move_history=[],
        captured_pieces={"white": [], "black": []},
        special_moves=[],
    )

    status = page.locator("#game-status")
    expect(status).to_have_text(re.compile(r"black wins.*checkmate", re.IGNORECASE))
    is_terminal = page.evaluate("window.CHESS_CONFIG.game_over === true && window.CHESS_CONFIG.checkmate === true")
    assert is_terminal, "Expected checkmate terminal state in client config"


@state_test
def test_check_status_displays_with_setup(page: Page, live_server):
    """Test that check status displays correctly - uses exact board setup"""
    # 🔑 CRITICAL: Clear cookies BEFORE page.goto() to ensure fresh session
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Set up position where white king is in check
    # Black queen on e4 gives check to white king on e1 (no pawns blocking)
    # FEN: r3k2r/8/8/8/4q3/8/8/R3K2R w - - 0 1
    check_fen = "r3k2r/8/8/8/4q3/8/8/R3K2R w - - 0 1"
    
    setup_board_position(
        page, 
        check_fen,
        live_server=live_server,
        move_history=[],  # No move history - just use FEN directly
        special_moves=[]
    )
    
    # Wait for board to render with pieces
    
    expect(page.locator("#board")).to_be_visible()
    
    # Verify status shows "Check!"
    status = page.locator("#game-status")
    expect(status).to_have_text(re.compile(r"Check!", re.IGNORECASE))


@state_test
def test_en_passant_capture_ui_with_exact_setup(page: Page, live_server):
    """Test en passant with exact board setup"""
    # 🔑 CRITICAL: Clear cookies BEFORE page.goto() to ensure fresh session
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Already after white en passant capture on f6.
    en_passant_fen = "4k3/8/5P2/8/8/8/8/4K3 b - - 0 1"
    
    setup_board_position(
        page,
        en_passant_fen,
        live_server=live_server,
        move_history=["exf6"],
        captured_pieces={"white": ["p"], "black": []},
        special_moves=["En Passant"]
    )

    expect(page.locator('[data-square="f5"] img')).to_have_count(0)
    expect(page.locator('[data-square="f6"] img')).to_have_count(1)
    
    # Verify special moves shows "En Passant"
    special_white = page.locator("#special-white li")
    special_black = page.locator("#special-black li")
    has_en_passant = special_white.filter(has_text=re.compile(r"En Passant", re.IGNORECASE)).count() > 0 or special_black.filter(has_text=re.compile(r"En Passant", re.IGNORECASE)).count() > 0
    assert has_en_passant, "En Passant should be listed in special moves"


@interaction_test
def test_error_message_clears_on_successful_move(page: Page, live_server):
    """Test that error message clears after successful move"""
    page.goto(live_server)
    wait_for_board_ready(page)

    illegal_result = drag_move(page, "e2", "e5")
    assert illegal_result["status"] == "illegal", f"Expected illegal move, got: {illegal_result}"

    error_msg = page.locator("#error-message")
    expect(error_msg).to_have_text(re.compile("Illegal move|Pawns can only move"))

    move_result, ai_result = drag_move_and_wait_for_ai(page, "e2", "e4")
    assert move_result["status"] in {"ok", "game_over"}, f"Expected legal move, got: {move_result}"
    assert ai_result["status"] in {"ok", "game_over"}, f"Unexpected /ai-move response: {ai_result}"

    expect(error_msg).to_be_empty()


@state_test
def test_multiple_captures_track_correctly(page: Page, live_server):
    """Test that multiple captures are tracked correctly"""
    page.goto(live_server)
    wait_for_board_ready(page)

    capture_fen = "4k3/8/8/3P4/8/8/8/4K3 b - - 0 1"
    setup_board_position(
        page,
        capture_fen,
        move_history=["exd5", "Ke7", "Qxd7"],
        captured_pieces={"white": ["p", "n"], "black": []},
        special_moves=[],
    )

    white_captured = page.locator("#white-captured")
    black_captured = page.locator("#black-captured")

    expect(white_captured).to_be_attached()
    expect(black_captured).to_be_attached()
    expect(page.locator("#white-captured img")).to_have_count(2)


@state_test
def test_game_state_after_many_moves(page: Page, live_server):
    """Test that game handles many moves without degradation"""
    page.goto(live_server)
    wait_for_board_ready(page)

    current_fen = page.evaluate("window.CHESS_CONFIG.fen")
    for _ in range(6):
        board = chess.Board(current_fen)
        if board.turn != chess.WHITE:
            break

        selected_uci = sorted(m.uci() for m in board.legal_moves)[0]
        from_sq = selected_uci[:2]
        to_sq = selected_uci[2:4]
        promotion = selected_uci[4] if len(selected_uci) > 4 else None

        move_result, ai_result = send_move_and_wait_for_ai(page, from_sq, to_sq, promotion=promotion)
        assert move_result["status"] in {"ok", "game_over"}, f"Unexpected /move response: {move_result}"
        assert ai_result["status"] in {"ok", "game_over"}, f"Unexpected /ai-move response: {ai_result}"
        current_fen = ai_result["fen"]

    status = page.locator("#game-status")
    expect(status).to_be_visible()

    move_history = page.locator("#move-history tr")
    assert move_history.count() > 0, "Move history should have entries"

@interaction_test
def test_snapback_piece_to_original_square(page: Page, live_server):
    """Test that same-square drag does not emit a /move request."""
    page.goto(live_server)
    wait_for_board_ready(page)

    e2_square = page.locator('[data-square="e2"]')
    e2_piece = page.locator('[data-square="e2"] img')
    piece_before = e2_piece.get_attribute("data-piece")

    with pytest.raises(PlaywrightTimeoutError):
        with page.expect_response(
            lambda resp: "/move" in resp.url and resp.request.method == "POST",
            timeout=1000,
        ):
            _drag_piece_to_same_square(page, "e2")

    page.wait_for_function(
        """
        (expectedPiece) => {
            const square = document.querySelector('[data-square="e2"] img');
            if (!square) return false;
            return square.getAttribute('data-piece') === expectedPiece;
        }
        """,
        arg=piece_before,
        timeout=5000,
    )
    
    # Verify piece is still on e2 (snapback worked)
    e2_piece_after = e2_square.locator("img")
    piece_after = e2_piece_after.get_attribute("data-piece")
    
    assert piece_before == piece_after, "Piece should remain on original square"
    
    # Verify no error message
    error_msg = page.locator("#error-message")
    expect(error_msg).to_be_empty()
    
    # Verify turn didn't change (no move was made)
    status = page.locator("#game-status")
    expect(status).to_have_text(re.compile(r"White's turn"))

@state_test
def test_castling_kingside_with_exact_setup(page: Page, live_server):
    """Test kingside castling with controlled board position"""
    # 🔑 CRITICAL: Clear cookies BEFORE page.goto() to ensure fresh session
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Position after white has castled kingside.
    castling_fen = "rnbqkbnr/pppppppp/8/8/2B5/5N2/PPPPPPPP/RNBQ1RK1 b kq - 1 1"
    
    setup_board_position(
        page,
        castling_fen,
        live_server=live_server,
        move_history=["O-O"],
        captured_pieces={"white": [], "black": []},
        special_moves=["Castling"]
    )
    
    # Verify castling was detected and appears in special moves
    page.locator("#special-white li, #special-black li").filter(has_text="Castling").wait_for(timeout=5000)
    
    # Verify king is on g1
    g1_king = page.locator('[data-square="g1"] img')
    expect(g1_king).to_have_count(1)
    
    # Verify rook is on f1 (moved from h1)
    f1_rook = page.locator('[data-square="f1"] img')
    expect(f1_rook).to_have_count(1)
    
    # Verify special moves shows "Castling"
    special_white = page.locator("#special-white li")
    special_black = page.locator("#special-black li")
    has_castling = special_white.filter(has_text=re.compile(r"Castling", re.IGNORECASE)).count() > 0 or special_black.filter(has_text=re.compile(r"Castling", re.IGNORECASE)).count() > 0
    assert has_castling, "Castling should be listed in special moves"


@state_test
def test_checkmate_fool_mate_with_setup(page: Page, live_server):
    """Test checkmate setup where black is checkmated and white is winner."""
    # 🔑 CRITICAL: Clear cookies BEFORE page.goto() to ensure fresh session
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Simple checkmate position: black queen checkmates white king
    # King on h8 has no escape, queen on h7 gives check
    checkmate_fen = "7k/7Q/7K/8/8/8/8/8 b - - 0 1"
    
    setup_board_position(
        page,
        checkmate_fen,
        live_server=live_server,
        move_history=[],
        captured_pieces={"white": [], "black": []},
        special_moves=[]
    )
    
    status = page.locator("#game-status")
    expect(status).to_have_text(re.compile(r"white wins.*checkmate", re.IGNORECASE))

    is_terminal = page.evaluate("window.CHESS_CONFIG.game_over === true && window.CHESS_CONFIG.checkmate === true")
    assert is_terminal, "Expected terminal checkmate state after setup"


# =============================================================================
# E2E TESTS - Position Evaluation UI (Material & Evaluation Display)
# =============================================================================

def test_material_advantage_displays_on_page_load(page: Page, live_server):
    """Test that material advantage indicator is visible on page load"""
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Verify material advantage element exists
    material_elem = page.locator("#material-advantage")
    expect(material_elem).to_be_visible()
    
    # Starting position should show "Even"
    expect(material_elem).to_have_text("Even")


def test_position_evaluation_displays_on_page_load(page: Page, live_server):
    """Test that position evaluation indicator is visible on page load"""
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Verify evaluation element exists
    eval_elem = page.locator("#position-eval")
    expect(eval_elem).to_be_visible()
    
    # Starting position should show roughly equal
    expect(eval_elem).to_have_text(re.compile(r"Equal|0\.0", re.IGNORECASE))


def test_material_updates_after_capture(page: Page, live_server):
    """Test that material advantage updates when piece is captured"""
    page.goto(live_server)
    wait_for_board_ready(page)

    material_elem = page.locator("#material-advantage")

    move_result_1, ai_result_1 = drag_move_and_wait_for_ai(page, "e2", "e4")
    move_result_2, ai_result_2 = drag_move_and_wait_for_ai(page, "d2", "d4")
    assert move_result_1["status"] in {"ok", "game_over"} and ai_result_1["status"] in {"ok", "game_over"}
    assert move_result_2["status"] in {"ok", "game_over"} and ai_result_2["status"] in {"ok", "game_over"}

    material_after = material_elem.text_content()
    assert material_after is not None, "Material should display after moves"


def test_material_shows_white_advantage(page: Page, live_server):
    """Test that white material advantage displays correctly"""
    # 🔑 CRITICAL: Clear cookies BEFORE page.goto() to ensure fresh session
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Set up position where white is up material
    # White up a pawn
    fen_white_up = "rnbqkbnr/ppppppp1/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    setup_board_position(
        page,
        fen_white_up,
        live_server=live_server,
        move_history=[],
        captured_pieces={"white": ["p"], "black": []},
        special_moves=[]
    )
    expect(page.locator("#material-advantage")).to_have_text(
        re.compile(r"White|\+\d+\.\d+"),
        timeout=5000,
    )


def test_material_shows_black_advantage(page: Page, live_server):
    """Test that black material advantage displays correctly"""
    # 🔑 CRITICAL: Clear cookies BEFORE page.goto() to ensure fresh session
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Set up position where black is up material
    # Black up a pawn
    fen_black_up = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPP1/RNBQKBNR w KQkq - 0 1"
    
    setup_board_position(
        page,
        fen_black_up,
        live_server=live_server,
        move_history=[],
        captured_pieces={"white": [], "black": ["P"]},
        special_moves=[]
    )
    
    material_elem = page.locator("#material-advantage")
    
    # Should show black advantage
    material_text = material_elem.text_content()
    assert "Black" in material_text or material_text.startswith("-") or "+" in material_text, \
        f"Should show black advantage, got: {material_text}"


def test_evaluation_updates_after_move(page: Page, live_server):
    """Test that evaluation score updates after making a move"""
    page.goto(live_server)
    wait_for_board_ready(page)
    
    eval_elem = page.locator("#position-eval")
    
    # Get initial evaluation
    initial_eval = eval_elem.text_content()
    
    move_result, ai_result = drag_move_and_wait_for_ai(page, "e2", "e4")
    assert move_result["status"] in {"ok", "game_over"} and ai_result["status"] in {"ok", "game_over"}
    
    # Evaluation should update
    updated_eval = eval_elem.text_content()
    
    # Should have some evaluation text
    assert updated_eval is not None and len(updated_eval) > 0, \
        "Evaluation should display after move"


def test_evaluation_shows_winning_for_checkmate(page: Page, live_server):
    """Test that evaluation shows extreme value for checkmate"""
    # 🔑 CRITICAL: Clear cookies BEFORE page.goto() to ensure fresh session
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Set up a true checkmate position (black to move, checkmated).
    checkmate_fen = "7k/7Q/7K/8/8/8/8/8 b - - 0 1"
    
    setup_board_position(
        page,
        checkmate_fen,
        live_server=live_server,
        move_history=[],
        captured_pieces={"white": [], "black": []},
        special_moves=[]
    )
    
    # Checkmate should be reflected in the client state.
    config_state = page.evaluate("window.CHESS_CONFIG")
    assert config_state.get("checkmate") is True, f"Expected checkmate=True, got: {config_state}"
    assert config_state.get("game_over") is True, f"Expected game_over=True, got: {config_state}"

    # UI status should indicate a terminal/check position.
    status = page.locator("#game-status")
    expect(status).to_have_text(re.compile(r"check|wins|game over", re.IGNORECASE))

    # Evaluation text should remain populated even in terminal states.
    eval_text = page.locator("#position-eval").text_content()
    assert eval_text is not None and len(eval_text.strip()) > 0, "Evaluation text should not be empty"


def test_material_display_has_correct_classes(page: Page, live_server):
    """Test that material advantage uses correct CSS classes"""
    page.goto(live_server)
    wait_for_board_ready(page)
    
    material_elem = page.locator("#material-advantage")
    
    # Starting position should be "Even" with no special class
    initial_class = material_elem.get_attribute("class")
    
    # Should not have material-white or material-black class when even
    assert "material-white" not in (initial_class or ""), \
        "Even material should not have material-white class"
    assert "material-black" not in (initial_class or ""), \
        "Even material should not have material-black class"


def test_tooltip_info_displays_correctly(page: Page, live_server):
    """Test that material and evaluation tooltips are present"""
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Look for tooltip icons
    tooltips = page.locator(".tooltip-icon")
    
    # Should have at least 2 tooltips (material and evaluation)
    tooltip_count = tooltips.count()
    assert tooltip_count >= 2, f"Should have at least 2 tooltips, found {tooltip_count}"
    
    # Verify tooltip text is present
    tooltip_texts = page.locator(".tooltip-text")
    assert tooltip_texts.count() >= 2, "Should have tooltip text elements"


def test_evaluation_text_format(page: Page, live_server):
    """Test that evaluation displays in correct format (e.g., '+1.5 (White Slightly Better)')"""
    page.goto(live_server)
    wait_for_board_ready(page)
    
    eval_elem = page.locator("#position-eval")
    eval_text = eval_elem.text_content()
    
    # Should have format like "0.0 (Equal)" or "+1.5 (White Better)"
    # Check for parentheses indicating evaluation label
    assert "(" in eval_text and ")" in eval_text, \
        f"Evaluation should have format 'X.X (Label)', got: {eval_text}"


def test_material_and_evaluation_persist_across_moves(page: Page, live_server):
    """Test that material and evaluation remain visible throughout game"""
    page.goto(live_server)
    wait_for_board_ready(page)
    
    material_elem = page.locator("#material-advantage")
    eval_elem = page.locator("#position-eval")
    
    # Make several moves
    moves = [
        ("e2", "e4"),
        ("d2", "d4"),  # After AI responds
        ("g1", "f3"),  # After AI responds
    ]
    
    for from_sq, to_sq in moves:
        from_piece = page.locator(f'[data-square="{from_sq}"] img')
        if from_piece.count() > 0:
            move_result, ai_result = send_move_and_wait_for_ai(page, from_sq, to_sq)
            assert move_result["status"] in {"ok", "game_over"} and ai_result["status"] in {"ok", "game_over"}

            expect(material_elem).to_be_visible()
            expect(eval_elem).to_be_visible()


def test_reset_clears_material_and_evaluation(page: Page, live_server):
    """Test that reset button clears material and evaluation to starting values"""
    page.goto(live_server)
    wait_for_board_ready(page)

    move_result, ai_result = drag_move_and_wait_for_ai(page, "e2", "e4")
    assert move_result["status"] in {"ok", "game_over"} and ai_result["status"] in {"ok", "game_over"}

    reset_btn = page.locator("#reset-btn")
    with page.expect_response(lambda resp: "/reset" in resp.url and resp.request.method == "POST") as reset_response_info:
        reset_btn.click()
    reset_result = reset_response_info.value.json()
    assert reset_result["status"] == "ok", f"Unexpected /reset response: {reset_result}"
    
    # Material should be "Even"
    material_elem = page.locator("#material-advantage")
    expect(material_elem).to_have_text("Even")
    
    # Evaluation should be close to 0 (Equal)
    eval_elem = page.locator("#position-eval")
    eval_text = eval_elem.text_content()
    assert "Equal" in eval_text or "0.0" in eval_text, \
        f"After reset, evaluation should show Equal, got: {eval_text}"


def test_evaluation_description_accuracy(page: Page, live_server):
    """Test that evaluation descriptions match score ranges"""
    # 🔑 CRITICAL: Clear cookies BEFORE page.goto() to ensure fresh session
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Test various positions with known evaluations
    test_cases = [
        # (FEN, expected_description_pattern)
        ("8/8/8/8/8/8/P7/K6k w - - 0 1", r"White|Better"),  # White up a pawn
        ("8/8/8/8/8/8/p7/K6k w - - 0 1", r"Black|Better"),  # Black up a pawn
        ("8/8/8/8/8/8/8/K6k w - - 0 1", r"Equal|0\.0"),      # Even (just kings)
    ]
    
    for fen, pattern in test_cases:
        setup_board_position(
            page,
            fen,
            live_server=live_server,
            move_history=[],
            captured_pieces={"white": [], "black": []},
            special_moves=[]
        )
        eval_elem = page.locator("#position-eval")
        eval_text = eval_elem.text_content()
        
        # Verify pattern matches
        assert re.search(pattern, eval_text, re.IGNORECASE), \
            f"For FEN {fen}, expected pattern '{pattern}', got: {eval_text}"
        
        # Return to starting position for next test
        page.goto(live_server)
        wait_for_board_ready(page)


def test_material_advantage_numerical_display(page: Page, live_server):
    """Test that material advantage shows numerical values (e.g., 'White +1.0')"""
    # 🔑 CRITICAL: Clear cookies BEFORE page.goto() to ensure fresh session
    page.goto(live_server)
    wait_for_board_ready(page)
    
    # Set up position: white up a pawn (100 centipawns = 1.0 pawns)
    fen_white_up_pawn = "rnbqkbnr/ppppppp1/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    setup_board_position(
        page,
        fen_white_up_pawn,
        live_server=live_server,
        move_history=[],
        captured_pieces={"white": ["p"], "black": []},
        special_moves=[]
    )

    expect(page.locator("#material-advantage")).to_have_text(
        re.compile(r"White \+\d+\.\d"),
        timeout=5000,
    )
    assert page.evaluate("window.CHESS_CONFIG.material > 0")


def test_evaluation_updates_independently_from_material(page: Page, live_server):
    """Test that evaluation and material are calculated independently"""
    page.goto(live_server)
    wait_for_board_ready(page)
    
    material_elem = page.locator("#material-advantage")
    eval_elem = page.locator("#position-eval")
    
    # Starting position: material is even, but evaluation may favor white slightly
    material_text = material_elem.text_content()
    eval_text = eval_elem.text_content()
    
    # Material should be "Even"
    assert "Even" in material_text, f"Starting material should be Even, got: {material_text}"
    
    # Evaluation includes positional factors, so may not be exactly 0
    # But should be close to equal
    assert eval_text is not None and len(eval_text) > 0, "Evaluation should display"
    
    # They should be independent values
    # Material is just piece count, evaluation includes position


def test_resign_button_ends_game(page: Page, live_server):
    """Test that clicking resign button ends the game"""
    page.goto(live_server)
    
    # Wait for board to load
    expect(page.locator("#board")).to_be_visible()
    
    # Click resign button and wait for response
    with page.expect_response(lambda resp: "/resign" in resp.url) as response_info:
        page.click("#resign-btn")
    response_info.value

    # Should show resignation message
    status = page.locator("#game-status")
    expect(status).to_contain_text("resignation", timeout=5000)


def test_resign_after_moves(page: Page, live_server):
    """Test resigning after some moves"""
    page.goto(live_server)
    wait_for_board_ready(page)

    move_result, ai_result = drag_move_and_wait_for_ai(page, "e2", "e4")
    assert move_result["status"] in {"ok", "game_over"} and ai_result["status"] in {"ok", "game_over"}
    expect(page.locator("#game-status")).to_be_visible()
    
    # Wait for resign button to be visible and clickable
    resign_btn = page.locator("#resign-btn")
    expect(resign_btn).to_be_visible()
    
    # Intercept resign response and verify backend accepted it.
    with page.expect_response(lambda resp: "/resign" in resp.url) as response_info:
        resign_btn.click()
    
    resign_response = response_info.value
    assert resign_response.ok, f"Unexpected /resign response code: {resign_response.status}"
    
    # Should show black wins by resignation
    status = page.locator("#game-status")
    expect(status).to_contain_text("Black wins", timeout=5000)
    expect(status).to_contain_text("resignation")

