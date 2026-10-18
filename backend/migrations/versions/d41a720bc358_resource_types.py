"""Persist custom booking resource types."""
from alembic import op
import sqlalchemy as sa

revision = "d41a720bc358"
down_revision = "f32b761a902d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "booking_resource_types",
        sa.Column("kind", sa.String(30), primary_key=True),
        sa.Column("label", sa.String(120), nullable=False, unique=True),
    )


def downgrade():
    op.drop_table("booking_resource_types")
