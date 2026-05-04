"""sync_schema — align DB with SQLAlchemy models

Revision ID: 0004_sync_schema
Revises: 0003_audit_log
Create Date: 2026-01-03 00:00:00.000000

Fixes detected by `alembic check` after initial migrations:
  - created_at / updated_at should be NOT NULL (Mapped[datetime] in models)
  - journal_lines entry_id FK had ondelete=CASCADE in migration, not in model
  - users column sizes and enum name differ from model definition
  - audit_logs missing ix_audit_logs_user_id standalone index
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_sync_schema"
down_revision = "0003_audit_log"
branch_labels = None
depends_on = None

# Tables/columns where created_at must be NOT NULL
_CREATED_AT_TABLES = [
    "account_plans",
    "fiscal_years",
    "journal_entries",
    "journal_lines",
    "journals",
]
_UPDATED_AT_TABLES = ["account_plans", "journal_entries"]


def upgrade() -> None:
    # ── 1. NOT NULL on timestamp columns ────────────────────────────────────
    for table in _CREATED_AT_TABLES:
        op.alter_column(
            table, "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            existing_server_default=sa.func.now(),
        )
    for table in _UPDATED_AT_TABLES:
        op.alter_column(
            table, "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            existing_server_default=sa.func.now(),
        )

    # ── 2. journal_lines FK: drop CASCADE, recreate without ondelete ─────────
    op.execute("ALTER TABLE journal_lines DROP CONSTRAINT IF EXISTS journal_lines_entry_id_fkey")
    op.create_foreign_key(
        "journal_lines_entry_id_fkey",
        "journal_lines", "journal_entries",
        ["entry_id"], ["id"],
    )

    # ── 3. users: fix column sizes ────────────────────────────────────────────
    op.alter_column("users", "full_name",
                    existing_type=sa.String(120), type_=sa.String(128), nullable=False)
    op.alter_column("users", "email",
                    existing_type=sa.String(254), type_=sa.String(255), nullable=False)
    op.alter_column("users", "hashed_password",
                    existing_type=sa.String(128), type_=sa.String(255), nullable=False)

    # ── 4. users: rename enum type userrole → user_role_enum (idempotent) ───
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
                ALTER TYPE userrole RENAME TO user_role_enum;
            END IF;
        END $$
    """)

    # ── 5. users: replace separate unique constraints with unique indexes ──────
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_username")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_email")
    op.execute("DROP INDEX IF EXISTS ix_users_username")
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")

    # ── 6. audit_logs: add missing standalone user_id index ──────────────────
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id)")


def downgrade() -> None:
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index("ix_users_username", "users", ["username"], unique=False)
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_unique_constraint("uq_users_username", "users", ["username"])

    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role_enum') THEN
                ALTER TYPE user_role_enum RENAME TO userrole;
            END IF;
        END $$
    """)

    op.alter_column("users", "hashed_password",
                    existing_type=sa.String(255), type_=sa.String(128), nullable=False)
    op.alter_column("users", "email",
                    existing_type=sa.String(255), type_=sa.String(254), nullable=False)
    op.alter_column("users", "full_name",
                    existing_type=sa.String(128), type_=sa.String(120), nullable=False)

    op.drop_constraint("journal_lines_entry_id_fkey", "journal_lines", type_="foreignkey")
    op.create_foreign_key(
        "journal_lines_entry_id_fkey",
        "journal_lines", "journal_entries",
        ["entry_id"], ["id"],
        ondelete="CASCADE",
    )

    for table in reversed(_UPDATED_AT_TABLES):
        op.alter_column(table, "updated_at",
                        existing_type=sa.DateTime(timezone=True),
                        nullable=True,
                        existing_server_default=sa.func.now())
    for table in reversed(_CREATED_AT_TABLES):
        op.alter_column(table, "created_at",
                        existing_type=sa.DateTime(timezone=True),
                        nullable=True,
                        existing_server_default=sa.func.now())
