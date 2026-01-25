"""create workout_template_sets table

Revision ID: c632c076cf42
Revises: 8c0e1c33db53
Create Date: 2026-01-22

"""
from alembic import op
import sqlalchemy as sa


revision = "c632c076cf42"
down_revision = "8c0e1c33db53"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workout_template_sets",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "template_exercise_id",
            sa.Integer(),
            sa.ForeignKey("workout_template_exercises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        op.f("ix_workout_template_sets_template_exercise_id"),
        "workout_template_sets",
        ["template_exercise_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_workout_template_sets_template_exercise_id"), table_name="workout_template_sets")
    op.drop_table("workout_template_sets")
