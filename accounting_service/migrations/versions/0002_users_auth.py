"""users_auth

Revision ID: 0002_users_auth
Revises: 0001_initial
Create Date: 2026-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

revision = "0002_users_auth"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    existing_tables = inspector.get_table_names()

    if "users" in existing_tables:
        # Table already created by a previous create_all — nothing to do.
        return

    # Ensure enum type exists (may have been created by create_all)
    existing_enums = {e["name"] for e in inspector.get_enums()}
    if "userrole" not in existing_enums:
        op.execute("CREATE TYPE userrole AS ENUM ('ADMIN', 'ACCOUNTANT', 'AUDITOR')")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("hashed_password", sa.String(128), nullable=False),
        sa.Column(
            "role",
            sa.Enum("ADMIN", "ACCOUNTANT", "AUDITOR", name="userrole", create_type=False),
            nullable=False,
            server_default="ACCOUNTANT",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS userrole")
