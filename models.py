from datetime import datetime
from extensions import db
import uuid

class Game(db.Model):
    __tablename__ = 'game'

    id = db.Column(db.Integer, primary_key=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Lifecycle
    state = db.Column(db.String(20), nullable=False, default="active", index=True)

    result = db.Column(db.String(20))  # "1-0", "0-1", "1/2-1/2"
    termination_reason = db.Column(db.String(50))  # checkmate, stalemate, resign

    ai_enabled = db.Column(db.Boolean, default=True)

    # identity
    player_uuid = db.Column(db.String(36), nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, nullable=True)

class GameMove(db.Model):
    __tablename__ = 'game_moves'
    id = db.Column(db.Integer, primary_key=True)

    game_id = db.Column(db.Integer, db.ForeignKey("game.id", ondelete="CASCADE"), nullable=False)
    move_number = db.Column(db.Integer, nullable=False)

    color = db.Column(db.String(5))  # "white" or "black"
    san = db.Column(db.String(50), nullable=False)
    uci = db.Column(db.String(10), nullable=True)

    fen_after = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)