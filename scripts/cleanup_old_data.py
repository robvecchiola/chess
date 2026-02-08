import os
import sys
from datetime import datetime, timedelta
import sys
import shutil
import fnmatch

#for cache file deletion
total_bytes_deleted = 0

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

#--------------------------------------------------
# cache file deletion logic
#--------------------------------------------------
def get_size(path):
    """Returns size of a file or total size of directory in bytes."""
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total

def remove_path(path):
    global total_bytes_deleted
    if os.path.exists(path):
        size = get_size(path)
        print(f"Removing: {path} ({size / (1024**2):.2f} MB)")
        total_bytes_deleted += size
        shutil.rmtree(path)

def remove_directories_by_name(root_dir, dir_name):
    global total_bytes_deleted
    for root, dirs, files in os.walk(root_dir):
        for dir in fnmatch.filter(dirs, dir_name):
            dir_path = os.path.join(root, dir)
            size = get_size(dir_path)
            print(f"Removing directory: {dir_path} ({size / (1024**2):.2f} MB)")
            total_bytes_deleted += size
            shutil.rmtree(dir_path)

def remove_files_by_extension(root_dir, file_extension):
    global total_bytes_deleted
    for root, dirs, files in os.walk(root_dir):
        for file in fnmatch.filter(files, file_extension):
            file_path = os.path.join(root, file)
            try:
                size = os.path.getsize(file_path)
                print(f"Removing file: {file_path} ({size / 1024:.2f} KB)")
                total_bytes_deleted += size
                os.remove(file_path)
            except OSError:
                pass

def remove_files_starting_with_tilde(root_dir):
    global total_bytes_deleted
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.startswith("~"):
                file_path = os.path.join(root, file)
                try:
                    size = os.path.getsize(file_path)
                    print(f"Removing temporary file: {file_path} ({size / 1024:.2f} KB)")
                    total_bytes_deleted += size
                    os.remove(file_path)
                except OSError:
                    pass
        for dir in dirs:
            if dir.startswith("~"):
                dir_path = os.path.join(root, dir)
                size = get_size(dir_path)
                print(f"Removing temporary directory: {dir_path} ({size / (1024**2):.2f} MB)")
                total_bytes_deleted += size
                shutil.rmtree(dir_path, ignore_errors=True)

def clean_home_cache():
    global total_bytes_deleted
    home_cache = os.path.expanduser('~/.cache/')
    if os.path.exists(home_cache):
        for item in os.listdir(home_cache):
            item_path = os.path.join(home_cache, item)
            try:
                size = get_size(item_path)
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                print(f"Removed: {item_path} ({size / (1024**2):.2f} MB)")
                total_bytes_deleted += size
            except Exception as e:
                print(f"Failed to remove {item_path}: {e}")


# -------------------------------------------------
# ENTRYPOINT (CRON SAFE)
# -------------------------------------------------

if __name__ == "__main__":
    root_dir = '/home/casualchess/'
    app = create_app()

    with app.app_context():
        cleanup_games()
        cleanup_sessions()
        remove_directories_by_name(root_dir, "__pycache__")
        remove_files_by_extension(root_dir, "*.log")
        remove_files_by_extension(root_dir, "*.tmp")
        remove_directories_by_name(root_dir, ".cache")
        remove_files_starting_with_tilde(root_dir)
        remove_files_by_extension(root_dir, "*.bak")
        remove_files_by_extension(root_dir, "*.pyc")
        remove_files_by_extension(root_dir, "*.pyo")
        remove_files_by_extension(root_dir, "*~")
        remove_files_by_extension(root_dir, "*.swp")
        remove_files_by_extension(root_dir, "*.swo")
        remove_path(os.path.expanduser("~/.npm"))
        remove_path(os.path.expanduser("~/.cache/pip"))
        clean_home_cache()

        # Summary
        print(f"\nClean-up completed. Total space freed: {total_bytes_deleted / (1024 ** 2):.2f} MB")
