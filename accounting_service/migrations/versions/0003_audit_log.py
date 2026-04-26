"""audit_log

Revision ID: 0003_audit_log
Revises: 0002_users_auth
Create Date: 2026-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

revision = "0003_audit_log"
down_revision = "0002_users_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)

    if "audit_logs" in inspector.get_table_names():
        return

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("user_role", sa.String(20), nullable=True),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("request_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_user_timestamp", "audit_logs", ["user_id", "timestamp"])
    op.create_index("ix_audit_logs_path_method", "audit_logs", ["path", "method"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa_inspect(bind)
    if "audit_logs" not in inspector.get_table_names():
        return
    op.drop_index("ix_audit_logs_path_method", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_table("audit_logs")
