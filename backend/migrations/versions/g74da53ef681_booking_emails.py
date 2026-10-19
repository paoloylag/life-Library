"""Durable booking email outbox and delivery state."""
from alembic import op
import sqlalchemy as sa

revision = "g74da53ef681"
down_revision = "f63c942de570"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("booking_emails",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dedupe_key", sa.String(160), nullable=False, unique=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("facility_bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_id", sa.String(255)),
        sa.Column("last_error", sa.String(255)))
    for field in ("booking_id", "recipient", "state", "next_attempt_at", "provider_id"):
        op.create_index("ix_booking_emails_" + field, "booking_emails", [field])


def downgrade():
    op.drop_table("booking_emails")
