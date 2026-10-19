"""Encrypted Google Calendar connections and durable booking sync queue."""
from alembic import op
import sqlalchemy as sa

revision = "f63c942de570"
down_revision = "e52b831cd469"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("google_calendar_connections",
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),primary_key=True),
        sa.Column("email",sa.String(255),nullable=False),
        sa.Column("refresh_token_encrypted",sa.Text(),nullable=False),
        sa.Column("needs_reconnect",sa.Boolean(),nullable=False),
        sa.Column("connected_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("booking_calendar_sync",
        sa.Column("booking_id",sa.Integer(),sa.ForeignKey("facility_bookings.id",ondelete="CASCADE"),primary_key=True),
        sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False,index=True),
        sa.Column("state",sa.String(20),nullable=False),sa.Column("attempts",sa.Integer(),nullable=False),
        sa.Column("next_attempt_at",sa.DateTime(timezone=True),nullable=False,index=True),
        sa.Column("event_id",sa.String(64),nullable=False),sa.Column("event_url",sa.String(1000)),
        sa.Column("last_error",sa.String(255)))


def downgrade():
    op.drop_table("booking_calendar_sync")
    op.drop_table("google_calendar_connections")
