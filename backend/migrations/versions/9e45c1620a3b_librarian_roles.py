"""Add librarian roles and mark local test accounts.

Revision ID: 9e45c1620a3b
Revises: 65b1a08d0c6d
"""

import sqlalchemy as sa
from alembic import op

revision = "9e45c1620a3b"
down_revision = "65b1a08d0c6d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("librarians", sa.Column("role", sa.String(20), nullable=False, server_default="librarian"))
    op.add_column("librarians", sa.Column("is_development", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("librarians", "is_development")
    op.drop_column("librarians", "role")
