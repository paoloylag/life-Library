"""expand library user profiles

Revision ID: 84cdb4f81c21
Revises: fbc5614d6f66
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "84cdb4f81c21"
down_revision: Union[str, Sequence[str], None] = "fbc5614d6f66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_profiles", sa.Column("year_level", sa.String(50), nullable=True))
    op.add_column("student_profiles", sa.Column("department", sa.String(120), nullable=True))
    op.add_column("student_profiles", sa.Column("organization", sa.String(180), nullable=True))
    op.add_column("library_visits", sa.Column("purpose", sa.String(180), nullable=True))


def downgrade() -> None:
    op.drop_column("library_visits", "purpose")
    op.drop_column("student_profiles", "organization")
    op.drop_column("student_profiles", "department")
    op.drop_column("student_profiles", "year_level")
