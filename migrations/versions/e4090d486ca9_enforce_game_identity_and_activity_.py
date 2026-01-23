"""enforce game identity and activity fields

Revision ID: e4090d486ca9
Revises: 3d23bc682796
Create Date: 2026-01-22 06:14:39.448654

"""
from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic.
revision = 'e4090d486ca9'
down_revision = '3d23bc682796'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # -------------------------------------------------
    # 1) Backfill player_uuid where missing
    # -------------------------------------------------
    conn.execute(
        sa.text(
            """
            UPDATE game
            SET player_uuid = UUID()
            WHERE player_uuid IS NULL
            """
        )
    )

    # -------------------------------------------------
    # 2) Backfill state
    # -------------------------------------------------
    conn.execute(
        sa.text(
            """
            UPDATE game
            SET state =
                CASE
                    WHEN termination_reason IS NOT NULL THEN 'finished'
                    WHEN ended_at IS NOT NULL THEN 'finished'
                    ELSE 'active'
                END
            WHERE state IS NULL
            """
        )
    )

    # -------------------------------------------------
    # 3) Backfill last_activity_at
    # -------------------------------------------------
    conn.execute(
        sa.text(
            """
            UPDATE game
            SET last_activity_at =
                COALESCE(ended_at, started_at)
            WHERE last_activity_at IS NULL
            """
        )
    )

    # -------------------------------------------------
    # 4) Enforce NOT NULL (MySQL requires type)
    # -------------------------------------------------
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

    # -------------------------------------------------
    # 5) Indexes
    # -------------------------------------------------
    conn = op.get_bind()
    insp = sa.inspect(conn)

    existing_indexes = {idx["name"] for idx in insp.get_indexes("game")}

    if "ix_game_player_uuid" not in existing_indexes:
        op.create_index("ix_game_player_uuid", "game", ["player_uuid"])

    if "ix_game_state" not in existing_indexes:
        op.create_index("ix_game_state", "game", ["state"])

    if "ix_game_last_activity_at" not in existing_indexes:
        op.create_index("ix_game_last_activity_at", "game", ["last_activity_at"])


def downgrade():
    op.drop_index("ix_game_last_activity_at", table_name="game")
    op.drop_index("ix_game_state", table_name="game")
    op.drop_index("ix_game_player_uuid", table_name="game")

    op.alter_column(
        "game",
        "last_activity_at",
        existing_type=sa.DateTime(),
        nullable=True,
    )
    op.alter_column(
        "game",
        "state",
        existing_type=sa.String(length=20),
        nullable=True,
    )
    op.alter_column(
        "game",
        "player_uuid",
        existing_type=sa.String(length=36),
        nullable=True,
    )