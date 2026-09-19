"""Rename staff roles to librarian and librarian associate.

Revision ID: b4d718c70aa1
Revises: 9e45c1620a3b
"""

from alembic import op
import sqlalchemy as sa

revision = "b4d718c70aa1"
down_revision = "9e45c1620a3b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE librarians SET role = 'librarian_associate' WHERE role = 'librarian'")
    op.execute("UPDATE librarians SET role = 'librarian' WHERE role = 'admin'")
    op.execute("UPDATE librarians SET email = 'librarian_associate@dev.library.local', name = 'Development Librarian Associate' WHERE is_development = true AND email = 'librarian@dev.library.local'")
    op.execute("UPDATE librarians SET email = 'librarian@dev.library.local', name = 'Development Librarian' WHERE is_development = true AND email = 'admin@dev.library.local'")
    with op.batch_alter_table("librarians") as batch:
        batch.alter_column("role", existing_type=sa.String(20), type_=sa.String(30),
                           server_default="librarian_associate")


def downgrade() -> None:
    op.execute("UPDATE librarians SET email = 'admin@dev.library.local', name = 'Development Administrator' WHERE is_development = true AND email = 'librarian@dev.library.local'")
    op.execute("UPDATE librarians SET email = 'librarian@dev.library.local', name = 'Development Librarian' WHERE is_development = true AND email = 'librarian_associate@dev.library.local'")
    op.execute("UPDATE librarians SET role = 'admin' WHERE role = 'librarian'")
    op.execute("UPDATE librarians SET role = 'librarian' WHERE role = 'librarian_associate'")
    with op.batch_alter_table("librarians") as batch:
        batch.alter_column("role", existing_type=sa.String(30), type_=sa.String(20),
                           server_default="librarian")
