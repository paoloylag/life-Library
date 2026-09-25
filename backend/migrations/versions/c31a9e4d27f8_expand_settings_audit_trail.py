"""Expand the settings audit trail with actor and value snapshots.

Revision ID: c31a9e4d27f8
Revises: b4d718c70aa1
"""

import sqlalchemy as sa
from alembic import op

revision = "c31a9e4d27f8"
down_revision = "b4d718c70aa1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("library_settings_audit") as batch:
        batch.add_column(sa.Column("actor_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("actor_email", sa.String(255), nullable=True))
        batch.add_column(sa.Column("changed_fields", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("before_values", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("after_values", sa.JSON(), nullable=True))
        batch.create_foreign_key(
            "fk_library_settings_audit_actor_id_librarians",
            "librarians",
            ["actor_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("library_settings_audit") as batch:
        batch.drop_constraint(
            "fk_library_settings_audit_actor_id_librarians", type_="foreignkey"
        )
        batch.drop_column("after_values")
        batch.drop_column("before_values")
        batch.drop_column("changed_fields")
        batch.drop_column("actor_email")
        batch.drop_column("actor_id")
