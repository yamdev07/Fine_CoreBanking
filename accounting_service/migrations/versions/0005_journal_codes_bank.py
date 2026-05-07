"""add bank journal codes to journalcode enum

Revision ID: 0005_journal_codes_bank
Revises: 0004_sync_schema
Create Date: 2026-05-04 00:00:00.000000

Adds IB, TR, LC, FX values to the journalcode PostgreSQL enum
for use by commercial bank (PCEC) plan templates.
"""
from alembic import op

revision = "0005_journal_codes_bank"
down_revision = "0004_sync_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE journalcode ADD VALUE IF NOT EXISTS 'IB'")
    op.execute("ALTER TYPE journalcode ADD VALUE IF NOT EXISTS 'TR'")
    op.execute("ALTER TYPE journalcode ADD VALUE IF NOT EXISTS 'LC'")
    op.execute("ALTER TYPE journalcode ADD VALUE IF NOT EXISTS 'FX'")


def downgrade() -> None:
    # PostgreSQL ne supporte pas la suppression de valeurs d'enum.
    # Downgrade laissé volontairement vide.
    pass
