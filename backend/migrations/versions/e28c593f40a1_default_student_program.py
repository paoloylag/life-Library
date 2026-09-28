"""Default missing student programs to BS-ENTREP.

Revision ID: e28c593f40a1
Revises: d72e413a0b61
"""

from alembic import op
import sqlalchemy as sa

revision = "e28c593f40a1"
down_revision = "d72e413a0b61"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE student_profiles SET program = 'BS-ENTREP' "
            "WHERE user_type = 'student' "
            "AND (program IS NULL OR TRIM(program) = '')"
        )
    )


def downgrade() -> None:
    # Existing and defaulted BS-ENTREP values cannot be distinguished safely.
    pass
