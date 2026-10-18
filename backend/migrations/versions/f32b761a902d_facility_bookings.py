"""Add resource reservations independently of attendance QR sessions."""

from alembic import op
import sqlalchemy as sa

revision = "f32b761a902d"
down_revision = "c28f9e031bd5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "booking_resources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), unique=True, nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("max_minutes", sa.Integer(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "facility_bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "resource_id",
            sa.Integer(),
            sa.ForeignKey("booking_resources.id"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("participants", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
    )
    for column in ("resource_id", "starts_at", "ends_at"):
        op.create_index(f"ix_facility_bookings_{column}", "facility_bookings", [column])
    inventory = sa.table(
        'booking_resources', sa.column('name', sa.String), sa.column('kind', sa.String),
        sa.column('duration_minutes', sa.Integer), sa.column('max_minutes', sa.Integer),
        sa.column('capacity', sa.Integer), sa.column('is_active', sa.Boolean),
    )
    op.bulk_insert(inventory, [
        *[dict(name=f'Nap Pod {number}', kind='nap_pod', duration_minutes=45, max_minutes=90, capacity=1, is_active=True) for number in range(1, 5)],
        *[dict(name=f'Collaboration Room {number}', kind='collaboration_room', duration_minutes=60, max_minutes=120, capacity=6, is_active=True) for number in range(1, 3)],
        dict(name='Computer 1', kind='computer', duration_minutes=120, max_minutes=120, capacity=1, is_active=True),
    ])


def downgrade():
    op.drop_table("facility_bookings")
    op.drop_table("booking_resources")
