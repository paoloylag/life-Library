"""Persist library settings and audit history.

Revision ID: 65b1a08d0c6d
Revises: 84cdb4f81c21
"""

import sqlalchemy as sa
from alembic import op

revision = "65b1a08d0c6d"
down_revision = "84cdb4f81c21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "library_configuration",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "library_settings_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("library_settings_audit")
    op.drop_table("library_configuration")
