"""initial schema

Revision ID: 001
Revises: 
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Authors table
    op.create_table(
        "authors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("messenger", sa.String(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("is_banned", sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("messenger", "chat_id"),
    )
    op.create_index(op.f('ix_authors_chat_id'), 'authors', ['chat_id'], unique=False)

    # Issues table
    op.create_table(
        "issues",
        sa.Column("tracker_key", sa.String(), nullable=False),
        sa.Column("summary", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("tags", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("result", sa.String(), nullable=True),
        sa.Column("tracker_text", sa.String(), nullable=True),
        sa.Column("assignee", sa.String(), nullable=True),
        sa.Column("resolved_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_answered", sa.Boolean(), nullable=False, default=False),
        sa.PrimaryKeyConstraint("tracker_key"),
    )
    op.create_index(op.f('ix_issues_tracker_key'), 'issues', ['tracker_key'], unique=False)

    # Closures table
    op.create_table(
        "closures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.Column("issue_id", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["authors.id"]),
        sa.ForeignKeyConstraint(["issue_id"], ["issues.tracker_key"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f('ix_closures_id'), 'closures', ['id'], unique=False)
    op.create_index(op.f('ix_closures_issue_id'), 'closures', ['issue_id'], unique=False)
    op.create_index(op.f('ix_closures_text'), 'closures', ['text'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_closures_text'), table_name='closures')
    op.drop_index(op.f('ix_closures_issue_id'), table_name='closures')
    op.drop_index(op.f('ix_closures_id'), table_name='closures')
    op.drop_table("closures")
    
    op.drop_index(op.f('ix_issues_tracker_key'), table_name='issues')
    op.drop_table("issues")
    
    op.drop_index(op.f('ix_authors_chat_id'), table_name='authors')
    op.drop_table("authors")