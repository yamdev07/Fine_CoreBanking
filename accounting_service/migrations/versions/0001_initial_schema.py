"""initial_schema

Revision ID: 0001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Exercices fiscaux ────────────────────────────────────────────────────
    op.create_table(
        "fiscal_years",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column(
            "status",
            sa.Enum("OPEN", "CLOSING", "CLOSED", name="fiscalyearstatus"),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.CheckConstraint("end_date > start_date", name="ck_fiscal_year_dates"),
    )

    # ── Périodes comptables ──────────────────────────────────────────────────
    op.create_table(
        "accounting_periods",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("fiscal_year_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column(
            "status",
            sa.Enum("OPEN", "CLOSED", "LOCKED", name="periodstatus"),
            nullable=False,
            server_default="OPEN",
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["fiscal_year_id"], ["fiscal_years.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fiscal_year_id", "name"),
        sa.CheckConstraint("end_date > start_date", name="ck_period_dates"),
    )
    op.create_index("ix_period_dates", "accounting_periods", ["start_date", "end_date"])

    # ── Plan de comptes ──────────────────────────────────────────────────────
    op.create_table(
        "account_plans",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("short_name", sa.String(50), nullable=True),
        sa.Column(
            "account_class",
            sa.Enum("CAPITAL","IMMOBILISE","STOCK","TIERS","TRESORERIE","CHARGES","PRODUITS","SPECIAUX","ANALYTIQUE", name="accountclass"),
            nullable=False,
        ),
        sa.Column(
            "account_type",
            sa.Enum("ACTIF","PASSIF","CHARGE","PRODUIT", name="accounttype"),
            nullable=False,
        ),
        sa.Column(
            "account_nature",
            sa.Enum("DEBITEUR","CREDITEUR", name="accountnature"),
            nullable=False,
        ),
        sa.Column("parent_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("level", sa.Integer, nullable=False, server_default="1"),
        sa.Column("path", sa.String(500), nullable=False, server_default=""),
        sa.Column("is_leaf", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("allow_manual_entry", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="XOF"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("budget_amount", sa.Numeric(20, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["parent_id"], ["account_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_account_code"),
    )
    op.create_index("ix_account_code", "account_plans", ["code"])
    op.create_index("ix_account_path", "account_plans", ["path"])
    op.create_index("ix_account_class", "account_plans", ["account_class"])

    # ── Journaux ─────────────────────────────────────────────────────────────
    op.create_table(
        "journals",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "journal_type",
            sa.Enum("GJ","CJ","BJ","OD","AN","EX","CR","EP", name="journalcode"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_sequence", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("sequence_prefix", sa.String(10), nullable=False, server_default=""),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    # ── Écritures comptables ─────────────────────────────────────────────────
    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("entry_number", sa.String(30), nullable=False),
        sa.Column("journal_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("period_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("value_date", sa.Date, nullable=False),
        sa.Column("posting_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("total_debit", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("total_credit", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="XOF"),
        sa.Column(
            "status",
            sa.Enum("DRAFT","POSTED","REVERSED", name="entrystatus"),
            nullable=False,
            server_default="DRAFT",
        ),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("posted_by", sa.String(100), nullable=True),
        sa.Column("reversed_by", sa.String(100), nullable=True),
        sa.Column("source_entry_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("source_service", sa.String(50), nullable=True),
        sa.Column("source_event_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["journal_id"], ["journals.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["accounting_periods.id"]),
        sa.ForeignKeyConstraint(["source_entry_id"], ["journal_entries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_number", name="uq_entry_number"),
        sa.UniqueConstraint("source_service", "source_event_id", name="uq_event_idempotence"),
        sa.CheckConstraint(
            "status != 'POSTED' OR total_debit = total_credit",
            name="ck_entry_balanced_when_posted"
        ),
    )
    op.create_index("ix_entry_date", "journal_entries", ["entry_date"])
    op.create_index("ix_entry_status", "journal_entries", ["status"])
    op.create_index("ix_entry_period", "journal_entries", ["period_id"])

    # ── Lignes d'écriture ─────────────────────────────────────────────────────
    op.create_table(
        "journal_lines",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("entry_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("line_number", sa.Integer, nullable=False),
        sa.Column("debit_amount", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("credit_amount", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="XOF"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("third_party_id", sa.String(100), nullable=True),
        sa.Column("third_party_type", sa.String(50), nullable=True),
        sa.Column("lettering_code", sa.String(20), nullable=True),
        sa.Column("lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lettered_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["entry_id"], ["journal_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["account_plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)",
            name="ck_line_debit_xor_credit"
        ),
        sa.CheckConstraint("debit_amount >= 0 AND credit_amount >= 0", name="ck_line_positive"),
    )
    op.create_index("ix_line_account", "journal_lines", ["account_id"])
    op.create_index("ix_line_lettering", "journal_lines", ["lettering_code"])
    op.create_index("ix_line_third_party", "journal_lines", ["third_party_id"])


def downgrade() -> None:
    op.drop_table("journal_lines")
    op.drop_table("journal_entries")
    op.drop_table("journals")
    op.drop_table("account_plans")
    op.drop_table("accounting_periods")
    op.drop_table("fiscal_years")
