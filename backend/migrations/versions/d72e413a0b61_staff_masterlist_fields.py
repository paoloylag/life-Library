"""Add staff masterlist profile fields.

Revision ID: d72e413a0b61
Revises: c31a9e4d27f8
"""
from alembic import op
import sqlalchemy as sa

revision = "d72e413a0b61"
down_revision = "c31a9e4d27f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_profiles", sa.Column("preferred_name", sa.String(120), nullable=True))
    op.add_column("student_profiles", sa.Column("employment_status", sa.String(80), nullable=True))
    op.add_column("student_profiles", sa.Column("position", sa.String(180), nullable=True))
    op.add_column("student_profiles", sa.Column("middle_name", sa.String(120), nullable=True))
    op.add_column("student_profiles", sa.Column("immediate_supervisor", sa.String(180), nullable=True))
    op.add_column("student_profiles", sa.Column("date_hired", sa.String(80), nullable=True))
    op.add_column("student_profiles", sa.Column("regularization_date", sa.String(80), nullable=True))
    op.add_column("student_profiles", sa.Column("contact_number", sa.String(80), nullable=True))


def downgrade() -> None:
    op.drop_column("student_profiles", "contact_number")
    op.drop_column("student_profiles", "regularization_date")
    op.drop_column("student_profiles", "date_hired")
    op.drop_column("student_profiles", "immediate_supervisor")
    op.drop_column("student_profiles", "middle_name")
    op.drop_column("student_profiles", "position")
    op.drop_column("student_profiles", "employment_status")
    op.drop_column("student_profiles", "preferred_name")
