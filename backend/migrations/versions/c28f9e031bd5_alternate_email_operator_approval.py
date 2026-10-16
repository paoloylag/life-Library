"""Allow audited operator approvals without a librarian login identity."""
from alembic import op
import sqlalchemy as sa

revision = "c28f9e031bd5"
down_revision = "b17e8d920ac4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("approved_google_emails") as batch:
        batch.alter_column("approved_by", existing_type=sa.Integer(), nullable=True)


def downgrade():
    # Operator approvals must first be reassigned to an actual librarian.
    with op.batch_alter_table("approved_google_emails") as batch:
        batch.alter_column("approved_by", existing_type=sa.Integer(), nullable=False)
