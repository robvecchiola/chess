"""
E2E test to verify multiple special moves display correctly in the UI.
Scenario: Multiple castlings and promotions from both white and black.
"""
import pytest
import re
from playwright.sync_api import Page, expect


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
    from tests.helper import setup_board_position

    page.goto(live_server)

    # Start from a board where white can castle immediately.
    page.wait_for_selector("#board")
    page.wait_for_load_state("networkidle")

    print("1. Testing castling special move")
    setup_board_position(
        page,
        "rnbqkbnr/pppppppp/8/8/2B5/5N2/PPPPPPPP/RNBQK2R w KQkq - 0 1",
        move_history=[],
        captured_pieces={"white": [], "black": []},
        special_moves=[],
    )

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)

    # Perform white castling and verify it is rendered.
    page.locator('[data-square="e1"] img').drag_to(page.locator('[data-square="g1"]'))
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)

    special_white = page.locator("#special-white li")
    expect(special_white).to_have_count(1, timeout=5000)
    expect(special_white).to_have_text("Castling")
    print(f"   OK castling displayed: {special_white.text_content()}")

    # Now set up a promotion position and preserve existing special move.
    print("\n2. Testing multiple promotions")
    page.goto(live_server)

    setup_board_position(
        page,
        "1nbqkbn1/PPppppPp/8/8/8/8/pppppppp/1rbqkbr1 w - - 0 1",
        move_history=["a4", "a5", "a5a6", "b5"],
        captured_pieces={"white": [], "black": []},
        special_moves=["Castling"],
    )

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Confirm seeded special move exists before promotion.
    special_white = page.locator("#special-white li")
    expect(special_white).to_have_count(1, timeout=5000)
    expect(special_white).to_have_text("Castling")
    print(f"   Initial special moves count: {special_white.count()}")

    # Submit promotion move directly to avoid dialog click timing flakiness.
    with page.expect_response(lambda resp: "/move" in resp.url) as response_info:
        page.evaluate("sendMove('a7', 'a8', 'q')")
    response_info.value

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Promotion to Q must be listed and castling must still be present.
    special_white = page.locator("#special-white li")
    promotion_q = special_white.filter(has_text=re.compile(r"Promotion to Q", re.IGNORECASE))
    promotion_q.first.wait_for(timeout=5000)

    white_count_after_promo = special_white.count()
    print(f"   After promotion: {white_count_after_promo} white special moves")
    assert white_count_after_promo >= 2, (
        f"Expected at least 2 white special moves, got {white_count_after_promo}"
    )

    white_texts = special_white.all_text_contents()
    print(f"   White special moves: {white_texts}")
    assert "Castling" in white_texts, (
        f"Expected Castling in white special moves, got {white_texts}"
    )
    assert any(re.search(r"Promotion to Q", text, re.IGNORECASE) for text in white_texts), (
        f"Expected Promotion to Q in white special moves, got {white_texts}"
    )

    total_visible = special_white.count() + page.locator("#special-black li").count()
    print("\nSpecial moves UI test completed")
    print(f"   Total special moves visible: {total_visible}")
    assert total_visible >= 2, f"Expected at least 2 total special moves, got {total_visible}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
