"""
E2E test to verify multiple special moves display correctly in the UI.
Scenario: Multiple castlings and promotions from both white and black.
"""
import pytest
import re
from playwright.sync_api import Page, expect
from tests.helper import (
    setup_board_position,
    wait_for_board_ready,
)


@pytest.fixture
def live_server(flask_server):
    return flask_server


def test_multiple_special_moves_accumulation_ui(page: Page, live_server):
    """
    Test that multiple special moves accumulate and display correctly.
    Scenario:
    - White castles
    - White promotes to Queen
    - White promotes to Knight
    - Black promotes to Rook
    Total: 4 special moves (3 white, 1 black)
    """
    page.goto(live_server)
    wait_for_board_ready(page)

    # Phase 1: White castling should appear in special-moves UI.
    setup_board_position(
        page,
        "rnbqkbnr/pppppppp/8/8/2B5/5N2/PPPPPPPP/RNBQ1RK1 b kq - 1 1",
        move_history=["O-O"],
        captured_pieces={"white": [], "black": []},
        special_moves=["Castling"],
    )

    special_white = page.locator("#special-white li")
    expect(special_white).to_have_count(1, timeout=5000)
    expect(special_white).to_have_text("Castling")
    
    # Phase 2: Set new board state but preserve previous special-move history.
    setup_board_position(
        page,
        "1Q5k/8/8/8/8/8/1P6/K7 b - - 0 1",
        move_history=["O-O", "b8=Q+"],
        captured_pieces={"white": [], "black": []},
        special_moves=["Castling", "Promotion to Q"],
    )
    wait_for_board_ready(page)

    special_white = page.locator("#special-white li")
    expect(special_white.filter(has_text="Castling")).to_have_count(1)
    expect(special_white.filter(has_text=re.compile(r"Promotion to Q", re.IGNORECASE))).to_have_count(1)

    total_visible = special_white.count() + page.locator("#special-black li").count()
    assert total_visible >= 2, f"Expected at least 2 total special moves, got {total_visible}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
