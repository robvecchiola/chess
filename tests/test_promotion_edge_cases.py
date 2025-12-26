"""
Test cases for promotion edge cases and the bug fix for illegal promotion popups
These tests verify that the promotion dialog only appears for valid promotion moves
"""
import pytest
from playwright.sync_api import Page, expect
from tests.helper import setup_board_position


@pytest.fixture
def live_server(flask_server):
    """Base URL for E2E tests"""
    return flask_server


# =============================================================================
# BUG FIX TESTS - Promotion Dialog Should Not Appear for Illegal Moves
# =============================================================================

def test_promotion_popup_blocked_by_opponent_piece(page: Page, live_server):
    """
    BUG FIX TEST: Promotion dialog should NOT appear when pawn's path to 8th rank is blocked
    Tests the fix in detectPromotion() that checks if target square is occupied
    """
    page.goto(live_server)
    
    # Setup: White pawn on a7, black rook still on a8 (blocking)
    # This is an illegal move - pawn can't move straight when blocked
    fen = "r1bqkbnr/P1pppppp/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    setup_board_position(
        page,
        fen,
        move_history=["a4", "h6", "a5", "h5", "a6"],
        captured_pieces={"white": [], "black": []},
        special_moves=[]
    )
    
    page.wait_for_timeout(500)
    
    # Try to drag pawn straight to a8 (illegal - blocked by rook)
    page.locator('[data-square="a7"] .piece-417db').drag_to(
        page.locator('[data-square="a8"]')
    )
    
    page.wait_for_timeout(1500)
    
    # Promotion dialog should NOT appear (this was the bug)
    promotion_dialog = page.locator("#promotion-dialog")
    expect(promotion_dialog).not_to_be_visible()
    
    # Pawn should snap back to a7
    a7_pawn = page.locator('[data-square="a7"] .piece-417db[data-piece="wP"]')
    expect(a7_pawn).to_have_count(1)
    
    # Error message should appear
    error_msg = page.locator("#error-message")
    expect(error_msg).to_have_text("Illegal move!")


def test_promotion_popup_invalid_diagonal_no_capture(page: Page, live_server):
    """
    BUG FIX TEST: Promotion dialog should NOT appear for diagonal move when no piece to capture
    Tests the fix that validates capture target exists and is opponent's piece
    """
    page.goto(live_server)
    
    # Setup: White pawn on a7, b8 is EMPTY (no piece to capture)
    fen = "rn1qkbnr/Ppppppp1/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    setup_board_position(
        page,
        fen,
        move_history=["a4", "h6", "a5", "h5", "a6"],
        captured_pieces={"white": [], "black": []},
        special_moves=[]
    )
    
    page.wait_for_timeout(500)
    
    # Try to move pawn diagonally to b8 (illegal - no piece to capture)
    page.locator('[data-square="a7"] .piece-417db').drag_to(
        page.locator('[data-square="b8"]')
    )
    
    page.wait_for_timeout(1500)
    
    # Promotion dialog should NOT appear
    promotion_dialog = page.locator("#promotion-dialog")
    expect(promotion_dialog).not_to_be_visible()
    
    # Pawn should snap back
    a7_pawn = page.locator('[data-square="a7"] .piece-417db[data-piece="wP"]')
    expect(a7_pawn).to_have_count(1)


def test_promotion_popup_only_appears_for_valid_straight_move(page: Page, live_server):
    """
    Test that promotion dialog DOES appear when pawn legally moves straight to 8th rank
    """
    page.goto(live_server)
    
    # Setup: White pawn on a7, a8 is EMPTY
    fen = "1nbqkbnr/Ppppppp1/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    setup_board_position(
        page,
        fen,
        move_history=["a4", "h6", "a5", "h5", "a6"],
        captured_pieces={"white": [], "black": []},
        special_moves=[]
    )
    
    page.wait_for_timeout(500)
    
    # Move pawn straight to a8 (legal move)
    page.locator('[data-square="a7"] .piece-417db').drag_to(
        page.locator('[data-square="a8"]')
    )
    
    page.wait_for_timeout(1000)
    
    # Promotion dialog SHOULD appear for this legal move
    promotion_dialog = page.locator("#promotion-dialog")
    expect(promotion_dialog).to_be_visible()
    
    # Clean up - cancel promotion
    page.locator('#cancel-promotion').click()


def test_promotion_popup_appears_for_valid_capture(page: Page, live_server):
    """
    Test that promotion dialog DOES appear when pawn captures diagonally to 8th rank
    """
    page.goto(live_server)
    
    # Setup: White pawn on a7, black bishop on b8 (can capture)
    fen = "rb1qkbnr/Ppppppp1/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    setup_board_position(
        page,
        fen,
        move_history=["a4", "h6", "a5", "h5", "a6"],
        captured_pieces={"white": [], "black": []},
        special_moves=[]
    )
    
    page.wait_for_timeout(500)
    
    # Capture bishop and promote
    page.locator('[data-square="a7"] .piece-417db').drag_to(
        page.locator('[data-square="b8"]')
    )
    
    page.wait_for_timeout(1000)
    
    # Promotion dialog SHOULD appear
    promotion_dialog = page.locator("#promotion-dialog")
    expect(promotion_dialog).to_be_visible()
    
    # Clean up
    page.locator('#cancel-promotion').click()


def test_promotion_popup_not_for_capturing_own_piece(page: Page, live_server):
    """
    BUG FIX TEST: Dialog should NOT appear when trying to capture own piece diagonally
    """
    page.goto(live_server)
    
    # Setup: White pawn on a7, WHITE bishop on b8 (can't capture own piece)
    fen = "rB1qkbnr/Ppppppp1/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    setup_board_position(
        page,
        fen,
        move_history=[],
        captured_pieces={"white": [], "black": []},
        special_moves=[]
    )
    
    page.wait_for_timeout(500)
    
    # Try to "capture" own bishop (illegal)
    page.locator('[data-square="a7"] .piece-417db').drag_to(
        page.locator('[data-square="b8"]')
    )
    
    page.wait_for_timeout(1500)
    
    # Dialog should NOT appear
    promotion_dialog = page.locator("#promotion-dialog")
    expect(promotion_dialog).not_to_be_visible()


# =============================================================================
# BLACK PAWN PROMOTION TESTS
# =============================================================================

def test_black_pawn_promotion_straight_move(page: Page, live_server):
    """
    Test black pawn promotion (previous tests only covered white)
    Black pawns promote on rank 1
    """
    page.goto(live_server)
    
    # Setup: Black pawn on b2, b1 is empty, it's black's turn
    fen = "rnbqkbnr/pppppppp/8/8/8/8/1p6/RNBQKBNR b KQkq - 0 1"
    
    setup_board_position(
        page,
        fen,
        move_history=["b3"],  # White moved, now black's turn
        captured_pieces={"white": [], "black": []},
        special_moves=[]
    )
    
    page.wait_for_timeout(500)
    
    # Move black pawn to b1
    page.locator('[data-square="b2"] .piece-417db[data-piece="bp"]').drag_to(
        page.locator('[data-square="b1"]')
    )
    
    page.wait_for_timeout(1000)
    
    # Promotion dialog should appear
    promotion_dialog = page.locator("#promotion-dialog")
    expect(promotion_dialog).to_be_visible()
    
    # Select queen
    page.locator('button[data-piece="q"]').click()
    page.wait_for_timeout(2000)
    
    # Verify promotion in special moves
    special_status = page.locator("#special-move-status")
    special_text = special_status.text_content()
    assert "Promotion" in special_text


def test_black_pawn_promotion_blocked_no_popup(page: Page, live_server):
    """
    Test black pawn promotion blocked by piece - no popup should appear
    """
    page.goto(live_server)
    
    # Setup: Black pawn on b2, WHITE KNIGHT on b1 (blocking)
    fen = "rnbqkbnr/pppppppp/8/8/8/8/1p6/RNBQKBNR b KQkq - 0 1"
    
    setup_board_position(
        page,
        fen,
        move_history=["b3"],
        captured_pieces={"white": [], "black": []},
        special_moves=[]
    )
    
    page.wait_for_timeout(500)
    
    # Try to move black pawn straight to b1 (blocked by knight)
    page.locator('[data-square="b2"] .piece-417db').drag_to(
        page.locator('[data-square="b1"]')
    )
    
    page.wait_for_timeout(1500)
    
    # Dialog should NOT appear (blocked square)
    promotion_dialog = page.locator("#promotion-dialog")
    expect(promotion_dialog).not_to_be_visible()


# =============================================================================
# PROMOTION EDGE CASES
# =============================================================================

def test_promotion_all_piece_types(page: Page, live_server):
    """
    Test promotion to each piece type: Queen, Rook, Bishop, Knight
    """
    for piece_type, piece_key in [("Queen", "q"), ("Rook", "r"), ("Bishop", "b"), ("Knight", "n")]:
        page.goto(live_server)
        
        # Fresh setup for each test
        fen = "1nbqkbnr/Ppppppp1/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1"
        
        setup_board_position(
            page,
            fen,
            move_history=[],
            captured_pieces={"white": [], "black": []},
            special_moves=[]
        )
        
        page.wait_for_timeout(500)
        
        # Promote pawn
        page.locator('[data-square="a7"] .piece-417db').drag_to(
            page.locator('[data-square="a8"]')
        )
        
        page.wait_for_timeout(1000)
        
        # Select piece type
        page.locator(f'button[data-piece="{piece_key}"]').click()
        page.wait_for_timeout(2000)
        
        # Verify promotion message
        special_status = page.locator("#special-move-status")
        special_text = special_status.text_content()
        assert "Promotion" in special_text, f"Failed for {piece_type}"
        assert piece_key.upper() in special_text, f"Expected {piece_type} in special moves"


def test_promotion_with_capture_updates_captured_pieces(page: Page, live_server):
    """
    Test that promoting with a capture correctly updates captured pieces list
    """
    page.goto(live_server)
    
    # Setup: White pawn on a7, black rook on b8
    fen = "rb1qkbnr/Ppppppp1/8/8/8/8/1PPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    setup_board_position(
        page,
        fen,
        move_history=[],
        captured_pieces={"white": [], "black": []},
        special_moves=[]
    )
    
    page.wait_for_timeout(500)
    
    # Capture rook and promote
    page.locator('[data-square="a7"] .piece-417db').drag_to(
        page.locator('[data-square="b8"]')
    )
    
    page.wait_for_timeout(1000)
    
    # Promote to queen
    page.locator('button[data-piece="q"]').click()
    page.wait_for_timeout(2000)
    
    # Verify rook was captured
    white_captured = page.locator("#white-captured")
    captured_text = white_captured.text_content()
    assert "r" in captured_text or "♜" in captured_text, "Black rook should be in white's captured pieces"
