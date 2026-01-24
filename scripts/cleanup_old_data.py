import os
import sys
from datetime import datetime, timedelta
import sys

print("Using Python:", sys.executable)

# -------------------------------------------------
# Ensure app imports work
# -------------------------------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)

from app import create_app
from extensions import db
from models import Game, GameMove
from sqlalchemy import func

# -------------------------------------------------
# CONFIG — SAFE DEFAULTS
# -------------------------------------------------

EMPTY_GAME_MAX_AGE_MINUTES = 5
ZOMBIE_GAME_MAX_AGE_MINUTES = 30
EXPLICIT_ABANDONED_MAX_AGE_MINUTES = 30

SESSION_MAX_AGE_MINUTES = 60

SESSION_DIR = os.path.join(BASE_DIR, "flask_session")

# -------------------------------------------------
# CLEANUP LOGIC
# -------------------------------------------------

def cleanup_games():
    now = datetime.utcnow()

    empty_cutoff = now - timedelta(minutes=EMPTY_GAME_MAX_AGE_MINUTES)
    zombie_cutoff = now - timedelta(minutes=ZOMBIE_GAME_MAX_AGE_MINUTES)
    abandoned_cutoff = now - timedelta(minutes=EXPLICIT_ABANDONED_MAX_AGE_MINUTES)

    # 1️⃣ Empty games (no moves, never ended)
    empty_games = (
        db.session.query(Game)
        .outerjoin(GameMove)
        .filter(GameMove.id.is_(None))
        .filter(Game.ended_at.is_(None))
        .filter(Game.started_at < empty_cutoff)
        .filter(Game.state == "active")
        .all()
    )

    # 2️⃣ Zombie games (moves exist, never ended, inactive)
    zombie_games = (
        db.session.query(Game)
        .join(GameMove)
        .filter(Game.ended_at.is_(None))
        .filter(Game.last_activity_at < zombie_cutoff)
        .filter(Game.state == "active")
        .all()
    )

    # 3️⃣ Explicitly abandoned games (already finalized)
    explicitly_abandoned_games = (
        db.session.query(Game)
        .filter(Game.state == "abandoned")
        .filter(Game.started_at < abandoned_cutoff)
        .all()
    )

    for game in empty_games + zombie_games + explicitly_abandoned_games:
        db.session.delete(game)

    db.session.commit()

    print(
        f"[DB] Deleted "
        f"{len(empty_games)} empty, "
        f"{len(zombie_games)} zombie, "
        f"{len(explicitly_abandoned_games)} abandoned games"
    )


def cleanup_sessions():
    if not os.path.exists(SESSION_DIR):
        print("[SESSION] No session directory found")
        return

    cutoff = datetime.utcnow() - timedelta(minutes=SESSION_MAX_AGE_MINUTES)
    deleted = 0

    for filename in os.listdir(SESSION_DIR):
        path = os.path.join(SESSION_DIR, filename)

        if not os.path.isfile(path):
            continue

        mtime = datetime.utcfromtimestamp(os.path.getmtime(path))

        if mtime < cutoff:
            os.remove(path)
            deleted += 1

    print(f"[SESSION] Deleted {deleted} old session files")


# -------------------------------------------------
# ENTRYPOINT (CRON SAFE)
# -------------------------------------------------

if __name__ == "__main__":
    app = create_app()

    with app.app_context():
        cleanup_games()
        cleanup_sessions()
