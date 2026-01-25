"""create workout_template_sets table

Revision ID: d460c425a92a
Revises: 986e5a82f446
Create Date: 2026-01-23 18:44:43.958148
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d460c425a92a"
down_revision: Union[str, Sequence[str], None] = "986e5a82f446"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workout_template_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_exercise_id", sa.Integer(), nullable=False),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["template_exercise_id"],
            ["workout_template_exercises.id"],
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_workout_template_sets_template_exercise_id",
        "workout_template_sets",
        ["template_exercise_id"],
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_workout_template_sets_template_exercise_id")
    op.execute("DROP TABLE IF EXISTS workout_template_sets")
