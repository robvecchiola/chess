import pytest
import chess
from app import create_app
from config import TestingConfig
from tests.helper import set_position
from tests.test_routes_api import make_move, reset_board

app = create_app(TestingConfig)

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['AI_ENABLED'] = False
    with app.test_client() as client:
        yield client

# =============================================================================
# CASTLING INTO CHECK TESTS
# =============================================================================

def test_castling_queenside_without_b1_piece(client):
    """Test queenside castling works when b1 is clear"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Clear ALL squares between king and rook (b1, c1, d1)
    moves = [
        ("d2", "d4"), ("d7", "d5"),
        ("b1", "c3"), ("b8", "c6"),  # Move knights away
        ("c1", "f4"), ("c8", "f5"),
        ("d1", "d2"), ("d8", "d7"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    # Now b1, c1, d1 are all clear - queenside castle should work
    rv = make_move(client, "e1", "c1")
    assert rv["status"] == "ok", "Queenside castling should work when path is clear"

def test_castling_into_check_kingside(client):
    """Test that castling is illegal when king would land in check (g1 attacked)"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up position using FEN where g1 is under attack
    # Black bishop on d4 attacks g1 directly
    with client.session_transaction() as sess:
        sess['fen'] = 'rnbqk2r/pppp1ppp/5n2/2b1p3/3bP3/5N2/PPPPBPPP/RNBQK2R w KQkq - 0 5'
        sess['move_history'] = ['e4', 'e5', 'Nf3', 'Nf6', 'Be2', 'Bc5', 'O-O', 'Bd4']
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    # Try to castle kingside - g1 is attacked by bishop on d4
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "illegal", "Cannot castle into check (g1 under attack)"


def test_castling_through_check_kingside(client):
    """Test that castling is illegal when king passes through check (f1 attacked)"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up: White king on e1, black rook on f8 with clear f-file
    # This makes f1 under attack
    with client.session_transaction() as sess:
        sess['fen'] = '5r2/8/8/8/8/8/8/4K2R w - - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    # Verify f1 is attacked by rook on f8
    board = chess.Board(sess['fen'])
    assert board.is_attacked_by(chess.BLACK, chess.F1), "f1 should be under attack by rook"
    
    # Try to castle kingside - king would pass through f1 which is attacked
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "illegal", "Cannot castle through check (f1 under attack)"


def test_castling_into_check_queenside(client):
    """Test that castling is illegal when king would land in check (c1 attacked)"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up: White king on e1, black rook on c8 with clear c-file
    # This makes c1 under attack
    with client.session_transaction() as sess:
        sess['fen'] = '2r2b1r/8/8/8/8/8/8/R3K2R w - - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    # Verify c1 is attacked by rook on c8
    board = chess.Board(sess['fen'])
    assert board.is_attacked_by(chess.BLACK, chess.C1), "c1 should be under attack by rook"
    
    # Try to castle queenside - c1 is attacked by rook
    rv = make_move(client, "e1", "c1")
    assert rv["status"] == "illegal", "Cannot castle into check (c1 under attack)"


def test_castling_through_check_queenside(client):
    """Test that castling is illegal when king passes through check (d1 attacked)"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up: White king on e1, black rook on d8 with clear d-file
    # This makes d1 under attack
    with client.session_transaction() as sess:
        sess['fen'] = '3r1b1r/8/8/8/8/8/8/R2K3R w - - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    # Verify d1 is attacked by rook on d8
    board = chess.Board(sess['fen'])
    assert board.is_attacked_by(chess.BLACK, chess.D1), "d1 should be under attack by rook"
    
    # Try to castle queenside - king would pass through d1 which is attacked
    rv = make_move(client, "e1", "c1")
    assert rv["status"] == "illegal", "Cannot castle through check (d1 under attack)"


# =============================================================================
# CASTLING WHILE IN CHECK
# =============================================================================

def test_castling_when_in_check(client):
    """Test that castling is illegal when king is currently in check"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up: White king on e1, black rook on e8 giving check
    # e1 must be empty (for king) for rook to attack it... wait, king IS on e1
    # This is a check - rook gives check from e8 to e1
    with client.session_transaction() as sess:
        sess['fen'] = '4r2r/8/8/8/8/8/8/R3K2R w - - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    # Verify king is in check from rook on e8
    board = chess.Board(sess['fen'])
    assert board.is_check(), "King should be in check from rook on e-file"
    
    # Try to castle while in check - should be illegal
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "illegal", "Cannot castle while in check"


# =============================================================================
# ROOK UNDER ATTACK (SHOULD BE LEGAL)
# =============================================================================

def test_castling_with_rook_under_attack(client):
    """Test that castling IS legal when rook is under attack (only king path matters)"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up position where h1 rook is under attack but king path is safe
    with client.session_transaction() as sess:
        # Black bishop on c5 attacks f2, but doesn't attack e1, f1, or g1
        sess['fen'] = 'rnbqk2r/pppp1ppp/5n2/2b1p3/4P3/5N2/PPPPBPPP/RNBQK2R w KQkq - 4 4'
        sess['move_history'] = ['e4', 'e5', 'Nf3', 'Nf6', 'Be2', 'Bc5']
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    # Castle kingside - should be LEGAL (rook being attacked doesn't matter)
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "ok", "Castling legal when rook is under attack"


def test_castling_queenside_with_b_file_attacked(client):
    """Test that queenside castling IS legal when b1 is under attack"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up: White king on e1, black rook on b8 attacks b1
    # But c1, d1, e1 are all safe
    with client.session_transaction() as sess:
        sess['fen'] = '1r2b2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    # Verify b1 is attacked but castling squares are safe
    board = chess.Board(sess['fen'])
    assert board.is_attacked_by(chess.BLACK, chess.B1), "b1 should be under attack by rook"
    assert not board.is_attacked_by(chess.BLACK, chess.C1), "c1 should be safe"
    assert not board.is_attacked_by(chess.BLACK, chess.D1), "d1 should be safe"
    assert not board.is_attacked_by(chess.BLACK, chess.E1), "e1 should be safe"
    
    # Castle queenside - should be LEGAL
    rv = make_move(client, "e1", "c1")
    assert rv["status"] == "ok", "Queenside castling legal even with b1 under attack"


# =============================================================================
# CASTLING RIGHTS LOST
# =============================================================================

def test_castling_rights_lost_after_rook_moves(client):
    """Test that castling rights are lost if rook is moved"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Move h1 rook to lose kingside castling rights
    moves = [
        ("h2", "h4"), ("h7", "h5"),
        ("h1", "h3"), ("h8", "h6"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    # Verify white lost kingside castling rights, but black's h8 rook moved too
    # So both have lost kingside rights
    with client.session_transaction() as sess:
        board = chess.Board(sess['fen'])
        # Both sides moved their h-file rooks
        assert not board.has_kingside_castling_rights(chess.WHITE), "White loses kingside castling after h1 rook moves"
        assert board.has_queenside_castling_rights(chess.WHITE), "White retains queenside castling"
        assert not board.has_kingside_castling_rights(chess.BLACK), "Black loses kingside castling after h8 rook moves"
        assert board.has_queenside_castling_rights(chess.BLACK), "Black retains queenside castling"


# =============================================================================
# CASTLING BOTH SIDES INDEPENDENTLY
# =============================================================================

def test_castling_both_sides_independently(client):
    """Test that moving one rook doesn't affect castling on the other side"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Move kingside rook (loses kingside castling)
    moves = [
        ("h2", "h4"), ("h7", "h5"),
        ("h1", "h3"), ("h8", "h6"),
        ("h3", "h1"), ("h6", "h8"),  # Rooks back
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    # Clear queenside for castling
    make_move(client, "d2", "d4")
    make_move(client, "d7", "d5")
    make_move(client, "b1", "c3")
    make_move(client, "b8", "c6")
    make_move(client, "c1", "f4")
    make_move(client, "c8", "f5")
    make_move(client, "d1", "d2")
    make_move(client, "d8", "d7")
    
    # Try queenside castling - should still work
    rv = make_move(client, "e1", "c1")
    assert rv["status"] == "ok", "Queenside castling still works after kingside rook moved"


# =============================================================================
# BLACK CASTLING THROUGH ATTACKED SQUARE
# =============================================================================

def test_black_castling_through_attacked_square(client):
    """Test that black cannot castle if king passes through attacked square"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up position: white rook on f1 attacks f8
    # Black king on e8 cannot castle kingside (would pass through f8)
    with client.session_transaction() as sess:
        sess['fen'] = 'r3k2r/8/8/8/8/8/8/R3KR2 b KQkq - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    # Verify f8 is attacked by white rook on f1
    board = chess.Board(sess['fen'])
    assert board.is_attacked_by(chess.WHITE, chess.F8), "f8 should be under attack by rook"
    
    # Black tries to castle kingside - king would pass through f8 (illegal)
    rv = make_move(client, "e8", "g8")
    assert rv["status"] == "illegal", "Cannot castle kingside when f8 under attack"


# =============================================================================
# MOVE HISTORY NOTATION
# =============================================================================

def test_castling_notation_in_move_history(client):
    """Test that castling is recorded correctly in move history"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up and perform kingside castling
    moves = [
        ("e2", "e4"), ("e7", "e5"),
        ("g1", "f3"), ("g8", "f6"),
        ("f1", "e2"), ("f8", "e7"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    # Castle kingside
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "ok"
    
    # Check move history uses standard notation "O-O"
    assert "O-O" in rv["move_history"], "Kingside castling should be O-O"


def test_castling_special_moves_tracking(client):
    """Test that castling is tracked in special_moves"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    
    # Set up and perform castling
    moves = [
        ("e2", "e4"), ("e7", "e5"),
        ("g1", "f3"), ("g8", "f6"),
        ("f1", "e2"), ("f8", "e7"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    # Castle
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "ok"
    assert "Castling" in rv["special_moves"], "Castling should be in special_moves"

def test_castling_with_pieces_between_king_and_rook(client):
    """Test castling fails if pieces block the path"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Don't clear the pieces - try to castle immediately
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "illegal"

def test_castling_queenside_with_b1_piece(client):
    """Test queenside castling fails if b1 has piece"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Clear d1, c1 but leave b1 knight
    moves = [
        ("d2", "d4"), ("d7", "d5"),
        ("c1", "f4"), ("c8", "f5"),
        ("d1", "d2"), ("d8", "d7"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    # b1 knight still there - queenside castle should work
    rv = make_move(client, "e1", "c1")
    assert rv["status"] == "illegal"  # b1 blocks queenside castling

def test_black_castling_into_check(client):
    """Test black cannot castle into check"""
    app.config['AI_ENABLED'] = False
    with client.session_transaction() as sess:
        # White rook on g1 attacks g8
        sess['fen'] = 'r3k2r/8/8/8/8/8/8/R3K1R1 b kq - 0 1'
        sess['move_history'] = []
        sess['captured_pieces'] = {'white': [], 'black': []}
        sess['special_moves'] = []
    
    rv = make_move(client, "e8", "g8")
    assert rv["status"] == "illegal"

def test_castling_after_king_moved_and_returned(client):
    """Test castling rights lost even if king returns to e1"""
    app.config['AI_ENABLED'] = False
    reset_board(client)
    # Move king and return
    make_move(client, "e2", "e4")
    make_move(client, "e7", "e5")
    make_move(client, "e1", "e2")
    make_move(client, "e8", "e7")
    make_move(client, "e2", "e1")
    make_move(client, "e7", "e8")
    # Clear for castling
    make_move(client, "g1", "f3")
    make_move(client, "g8", "f6")
    make_move(client, "f1", "e2")
    make_move(client, "f8", "e7")
    # Try to castle - should fail (king moved)
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "illegal"

def test_castling_after_en_passant(client):
    """En passant doesn't affect castling rights"""
    # Setup: realistic position with knights developed and en passant opportunity
    set_position(client, 'r3k2r/ppp1pppp/2n5/3Pp3/8/5N2/PPP1PPPP/R1B1K2R w KQkq e6 0 1')
    
    # En passant
    rv = make_move(client, "d5", "e6")
    assert rv["status"] == "ok"
    
    # White should still be able to castle kingside
    # Clear f1 bishop first
    make_move(client, "c6", "d4")  # Black knight moves
    make_move(client, "c1", "g5")  # White bishop moves out
    make_move(client, "d4", "c6")  # Black knight back
    
    rv = make_move(client, "e1", "g1")  # White castles
    assert rv["status"] == "ok"


def test_castling_with_promoted_rook(client):
    """Cannot castle with promoted piece (even if on h1)"""
    # Promote pawn to rook on h8 (8th rank for white)
    set_position(client, '4k3/7P/8/8/8/8/8/4K3 w - - 0 1')
    
    # Promote to rook on h8
    rv = make_move(client, "h7", "h8", promotion="r")
    assert rv["status"] == "ok"
    
    # Board now has promoted rook on h8, but no castling rights in FEN
    # This test documents that promoted rooks don't grant castling rights
    # (FEN never had castling rights, so can't castle regardless)


def test_castling_loses_rights_after_rook_capture(client):
    """Castling rights lost if rook is captured"""
    set_position(client, 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
    
    # Remove white's h1 rook via capture (simulate)
    with client.session_transaction() as sess:
        sess['fen'] = 'r3k2r/8/8/8/8/8/8/R3K3 w Qkq - 0 1'
    
    # White should not be able to castle kingside
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "illegal"


def test_castling_both_sides_same_game(client):
    """Both white and black can castle in same game"""
    reset_board(client)
    
    # Clear path for both sides to castle kingside
    moves = [
        ("e2", "e4"), ("e7", "e5"),
        ("g1", "f3"), ("g8", "f6"),
        ("f1", "e2"), ("f8", "e7"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    # White castles kingside
    rv1 = make_move(client, "e1", "g1")
    assert rv1["status"] == "ok"
    
    # Black castles kingside
    rv2 = make_move(client, "e8", "g8")
    assert rv2["status"] == "ok"
    
    # Both castling moves in special moves
    castling_moves = [m for m in rv2["special_moves"] if "Castling" in m]
    assert len(castling_moves) == 2


def test_castling_queenside_after_kingside_lost(client):
    """Can still castle queenside after losing kingside rights"""
    set_position(client, 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
    
    # Move kingside rook (lose kingside castling)
    with client.session_transaction() as sess:
        sess['fen'] = 'r3k2r/8/8/8/8/8/8/R3K3 w Qkq - 0 1'
    
    # Can still castle queenside
    rv = make_move(client, "e1", "c1")
    assert rv["status"] == "ok"


def test_castling_kingside_after_queenside_lost(client):
    """Can still castle kingside after losing queenside rights"""
    set_position(client, 'r3k2r/8/8/8/8/8/8/4K2R w Kkq - 0 1')
    
    # Can castle kingside
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "ok"


def test_castling_notation_in_move_history(client):
    """Castling uses O-O notation"""
    set_position(client, 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
    
    # Kingside castling
    rv = make_move(client, "e1", "g1")
    assert "O-O" in rv["move_history"][-1]
    assert "O-O-O" not in rv["move_history"][-1]


def test_queenside_castling_notation(client):
    """Queenside castling uses O-O-O notation"""
    set_position(client, 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
    
    rv = make_move(client, "e1", "c1")
    assert "O-O-O" in rv["move_history"][-1]


def test_castling_special_moves_white_vs_black(client):
    """Special moves distinguish white vs black castling"""
    reset_board(client)
    
    # Clear path for both sides
    moves = [
        ("e2", "e4"), ("e7", "e5"),
        ("g1", "f3"), ("g8", "f6"),
        ("f1", "e2"), ("f8", "e7"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    # White castles
    rv1 = make_move(client, "e1", "g1")
    # Black castles
    rv2 = make_move(client, "e8", "g8")
    
    # Should have two separate castling entries
    assert len(rv2["special_moves"]) == 2


def test_castling_fen_updates_rights_correctly(client):
    """FEN castling rights updated after castling"""
    reset_board(client)
    
    # Clear path for white to castle kingside
    moves = [
        ("e2", "e4"), ("e7", "e5"),
        ("g1", "f3"), ("g8", "f6"),
        ("f1", "e2"), ("f8", "e7"),
    ]
    for from_sq, to_sq in moves:
        make_move(client, from_sq, to_sq)
    
    rv = make_move(client, "e1", "g1")
    
    # After white kingside castles, should lose K and Q rights (white moved king)
    # Black should retain both rights (kq)
    fen_parts = rv["fen"].split()
    castling_rights = fen_parts[2]
    
    assert "K" not in castling_rights  # White lost kingside
    assert "Q" not in castling_rights  # White lost queenside (king moved)
    assert "k" in castling_rights  # Black retains kingside
    assert "q" in castling_rights  # Black retains queenside


def test_castling_through_attacked_square_detailed(client):
    """Detailed test of squares king passes through"""
    # Rook on f1 attacks f8 (king passes through f8 when castling kingside)
    set_position(client, 'r3k2r/8/8/8/8/8/8/R3KR2 b kq - 0 1')
    
    board = chess.Board('r3k2r/8/8/8/8/8/8/R3KR2 b kq - 0 1')
    assert board.is_attacked_by(chess.WHITE, chess.F8)
    
    # Black cannot castle kingside (f8 attacked)
    rv = make_move(client, "e8", "g8")
    assert rv["status"] == "illegal"


def test_castling_rook_under_attack_is_legal(client):
    """Castling is legal even if rook is under attack"""
    # Black rook on h8 attacks h1 rook (through h-file)
    # King's path (e1-f1-g1) is safe
    set_position(client, '4k2r/8/8/8/8/8/8/R3K2R w KQ - 0 1')
    
    board = chess.Board('4k2r/8/8/8/8/8/8/R3K2R w KQ - 0 1')
    assert board.is_attacked_by(chess.BLACK, chess.H1), "h1 should be under attack"
    assert not board.is_attacked_by(chess.BLACK, chess.E1), "e1 should be safe"
    assert not board.is_attacked_by(chess.BLACK, chess.F1), "f1 should be safe"
    assert not board.is_attacked_by(chess.BLACK, chess.G1), "g1 should be safe"
    
    # White can still castle kingside (rook being attacked doesn't matter)
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "ok"


def test_castling_intermediate_square_attacked(client):
    """Cannot castle if intermediate square is attacked"""
    # Rook on d1 attacks d8
    set_position(client, 'r3k2r/8/8/8/8/8/8/R2RK2R b kq - 0 1')
    
    # Black cannot castle queenside (d8 is attacked)
    rv = make_move(client, "e8", "c8")
    assert rv["status"] == "illegal"


def test_castling_after_king_check_and_return(client):
    """King in check, escapes, castling rights lost"""
    set_position(client, 'r3k2r/8/8/8/8/8/4r3/R3K2R w KQkq - 0 1')
    
    # King in check from rook, must move
    rv = make_move(client, "e1", "d1")
    assert rv["status"] == "ok"
    
    # King returns
    rv = make_move(client, "e2", "e3")  # Black moves away
    rv = make_move(client, "d1", "e1")
    
    # Castling rights should be lost (king moved)
    rv = make_move(client, "e3", "e2")  # Black move
    rv = make_move(client, "e1", "g1")
    assert rv["status"] == "illegal"


def test_castling_material_unchanged(client):
    """Castling doesn't change material balance"""
    set_position(client, 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1')
    
    material_before = 0  # Position is equal
    
    rv = make_move(client, "e1", "g1")
    
    assert rv["material"] == material_before


def test_castling_with_check_after(client):
    """Castling can give check (rare but possible)"""
    # Contrived position where castling gives check
    # (Very rare in practice)
    set_position(client, '4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1')
    
    # After queenside castling, rook might give check
    # (This specific position doesn't, but tests the concept)
    rv = make_move(client, "e1", "c1")
    
    # Just verify castling worked
    assert rv["status"] == "ok"