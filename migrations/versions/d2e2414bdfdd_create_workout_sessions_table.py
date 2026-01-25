"""create workout_sessions table

Revision ID: d2e2414bdfdd
Revises: 765e165a8d44
Create Date: 2026-01-21 17:48:55.631814

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e2414bdfdd'
down_revision: Union[str, Sequence[str], None] = '765e165a8d44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workout_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workout_sessions_user_id", "workout_sessions", ["user_id"])
    op.create_index("ix_workout_sessions_status", "workout_sessions", ["status"])



def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()

    # SQLite: only drop indexes if they exist
    idx_rows = conn.execute(sa.text("PRAGMA index_list('workout_sessions')")).fetchall()
    idx_names = {row[1] for row in idx_rows}  # row[1] is index name

    if "ix_workout_sessions_status" in idx_names:
        op.drop_index("ix_workout_sessions_status", table_name="workout_sessions")
    if "ix_workout_sessions_user_id" in idx_names:
        op.drop_index("ix_workout_sessions_user_id", table_name="workout_sessions")

    # Drop table only if it exists
    tbl_rows = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='workout_sessions'")
    ).fetchall()
    if tbl_rows:
        op.drop_table("workout_sessions")


