"""Approved alternate Google identities for existing library users."""
from alembic import op
import sqlalchemy as sa

revision = "b17e8d920ac4"
down_revision = "a19d6e74c2f1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("approved_google_emails",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("google_id", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("librarians.id"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_approved_google_emails_user_id", "approved_google_emails", ["user_id"])
    op.create_index("ix_approved_google_emails_email", "approved_google_emails", ["email"], unique=True)
    op.create_index("ix_approved_google_emails_google_id", "approved_google_emails", ["google_id"], unique=True)


def downgrade():
    op.drop_table("approved_google_emails")
