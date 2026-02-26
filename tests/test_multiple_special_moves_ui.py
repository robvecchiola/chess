"""
E2E test to verify multiple special moves display correctly in the UI.
Scenario: Multiple special moves from both white and black appear in separate lists.
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
    - White castling
    - White promotion
    - Black castling
    - Black promotion
    - Black en passant
    """
    page.goto(live_server)
    wait_for_board_ready(page)

    # Populate mixed-color special moves via the test endpoint.
    setup_board_position(
        page,
        "r3k2r/1P4P1/8/8/8/8/8/R3K2R w KQkq - 0 1",
        move_history=["O-O", "O-O", "b8=Q", "g1=R", "exf6 e.p."],
        captured_pieces={"white": [], "black": []},
        special_moves=[
            "White: Castling",
            "White: Promotion to Q",
            "Black: Castling",
            "Black: Promotion to R",
            "Black: En Passant",
        ],
    )
    wait_for_board_ready(page)

    special_white = page.locator("#special-white li")
    special_black = page.locator("#special-black li")

    expect(special_white).to_have_count(2, timeout=5000)
    expect(special_black).to_have_count(3, timeout=5000)

    expect(special_white.filter(has_text=re.compile(r"Castling", re.IGNORECASE))).to_have_count(1)
    expect(special_white.filter(has_text=re.compile(r"Promotion to Q", re.IGNORECASE))).to_have_count(1)
    expect(special_black.filter(has_text=re.compile(r"Castling", re.IGNORECASE))).to_have_count(1)
    expect(special_black.filter(has_text=re.compile(r"Promotion to R", re.IGNORECASE))).to_have_count(1)
    expect(special_black.filter(has_text=re.compile(r"En Passant", re.IGNORECASE))).to_have_count(1)

    expect(special_white.filter(has_text=re.compile(r"Promotion to R|En Passant", re.IGNORECASE))).to_have_count(0)
    expect(special_black.filter(has_text=re.compile(r"Promotion to Q", re.IGNORECASE))).to_have_count(0)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
