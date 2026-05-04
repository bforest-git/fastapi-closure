"""remove issue fields

Revision ID: 002
Revises: 001
Create Date: 2026-05-04 08:43:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove columns from issues table
    op.drop_column('issues', 'summary')
    op.drop_column('issues', 'description')
    op.drop_column('issues', 'tags')
    op.drop_column('issues', 'created_at')
    op.drop_column('issues', 'updated_at')


def downgrade() -> None:
    # Add columns back to issues table
    op.add_column('issues', sa.Column('summary', sa.String(), nullable=True))
    op.add_column('issues', sa.Column('description', sa.String(), nullable=True))
    op.add_column('issues', sa.Column('tags', sa.String(), nullable=True))
    op.add_column('issues', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('issues', sa.Column('updated_at', sa.DateTime(), nullable=True))