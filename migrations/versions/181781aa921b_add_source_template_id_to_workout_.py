"""add source_template_id to workout_sessions

Revision ID: 181781aa921b
Revises: d460c425a92a
Create Date: 2026-01-23 21:20:02.351297

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '181781aa921b'
down_revision: Union[str, Sequence[str], None] = 'd460c425a92a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Use batch mode for SQLite
    with op.batch_alter_table('workout_sessions', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('source_template_id', sa.Integer(), nullable=True)
        )
        batch_op.create_index(
            'ix_workout_sessions_source_template_id',
            ['source_template_id'],
            unique=False
        )
        batch_op.create_foreign_key(
            'fk_workout_sessions_source_template_id',
            'workout_templates',
            ['source_template_id'],
            ['id'],
            ondelete='SET NULL'
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Use batch mode for SQLite
    with op.batch_alter_table('workout_sessions', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_workout_sessions_source_template_id',
            type_='foreignkey'
        )
        batch_op.drop_index('ix_workout_sessions_source_template_id')
        batch_op.drop_column('source_template_id')
