"""add player identity and game state

Revision ID: 3d23bc682796
Revises: 9e2b718f5842
Create Date: 2026-01-22 05:58:27.068807
"""
from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic.
revision = "3d23bc682796"
down_revision = "9e2b718f5842"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Add columns as nullable first
    op.add_column(
        "game",
        sa.Column("player_uuid", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "game",
        sa.Column("state", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "game",
        sa.Column("last_activity_at", sa.DateTime(), nullable=True),
    )

    # 2) Backfill existing rows
    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            UPDATE game
            SET
                player_uuid = :uuid,
                state = 'finished',
                last_activity_at = COALESCE(ended_at, started_at)
            """
        ),
        {"uuid": str(uuid.uuid4())},
    )

    # 3) Enforce NOT NULL (MySQL requires existing_type)
    op.alter_column(
        "game",
        "player_uuid",
        existing_type=sa.String(length=36),
        nullable=False,
    )
    op.alter_column(
        "game",
        "state",
        existing_type=sa.String(length=20),
        nullable=False,
    )
    op.alter_column(
        "game",
        "last_activity_at",
        existing_type=sa.DateTime(),
        nullable=False,
    )

    # 4) Indexes
    op.create_index("ix_game_player_uuid", "game", ["player_uuid"])
    op.create_index("ix_game_state", "game", ["state"])
    op.create_index(
        "ix_game_last_activity_at",
        "game",
        ["last_activity_at"],
    )


def downgrade():
    op.drop_index("ix_game_last_activity_at", table_name="game")
    op.drop_index("ix_game_state", table_name="game")
    op.drop_index("ix_game_player_uuid", table_name="game")

    op.drop_column("game", "last_activity_at")
    op.drop_column("game", "state")
    op.drop_column("game", "player_uuid")
