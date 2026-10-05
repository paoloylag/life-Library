"""Remove unused staff profile fields.

Revision ID: a19d6e74c2f1
Revises: e28c593f40a1
"""
from alembic import op
import sqlalchemy as sa

revision = "a19d6e74c2f1"
down_revision = "e28c593f40a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("student_profiles", "regularization_date")
    op.drop_column("student_profiles", "date_hired")
    op.drop_column("student_profiles", "immediate_supervisor")
    op.drop_column("student_profiles", "position")
    op.drop_column("student_profiles", "employment_status")


def downgrade() -> None:
    op.add_column(
        "student_profiles",
        sa.Column("employment_status", sa.String(80), nullable=True),
    )
    op.add_column(
        "student_profiles", sa.Column("position", sa.String(180), nullable=True)
    )
    op.add_column(
        "student_profiles",
        sa.Column("immediate_supervisor", sa.String(180), nullable=True),
    )
    op.add_column(
        "student_profiles", sa.Column("date_hired", sa.String(80), nullable=True)
    )
    op.add_column(
        "student_profiles",
        sa.Column("regularization_date", sa.String(80), nullable=True),
    )
