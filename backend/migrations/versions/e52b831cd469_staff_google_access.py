"""Explicitly link Google library identities to staff permissions."""
from alembic import op
import sqlalchemy as sa

revision = "e52b831cd469"
down_revision = "d41a720bc358"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("staff_google_access",
        sa.Column("librarian_id", sa.Integer(), sa.ForeignKey("librarians.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True))


def downgrade():
    op.drop_table("staff_google_access")
