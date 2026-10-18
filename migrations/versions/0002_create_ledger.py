"""create ledger

Revision ID: 0002_create_ledger
Revises: 0001_create_users
Create Date: 2026-10-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_create_ledger"
down_revision: Union[str, Sequence[str], None] = "0001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("ledger_accounts", "ledger_entries", "ledger_lines")


def upgrade() -> None:
    op.create_table(
        "ledger_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("circle_ref", sa.String(length=64), nullable=True),
        sa.Column("member_ref", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('asset', 'liability', 'equity', 'income', 'expense')",
            name="ck_ledger_accounts_kind",
        ),
        sa.CheckConstraint("length(currency) = 3", name="ck_ledger_accounts_currency"),
        sa.UniqueConstraint("code", name="uq_ledger_accounts_code"),
    )
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("reversal_of_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["reversal_of_id"],
            ["ledger_entries.id"],
            name="fk_ledger_entries_reversal_of_id",
        ),
        sa.UniqueConstraint("reference", name="uq_ledger_entries_reference"),
        sa.UniqueConstraint("reversal_of_id", name="uq_ledger_entries_reversal_of_id"),
    )
    op.create_table(
        "ledger_lines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("entry_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(length=6), nullable=False),
        sa.Column("amount_pence", sa.BigInteger(), nullable=False),
        sa.Column("memo", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["ledger_entries.id"],
            name="fk_ledger_lines_entry_id",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["ledger_accounts.id"],
            name="fk_ledger_lines_account_id",
        ),
        sa.CheckConstraint(
            "direction IN ('debit', 'credit')",
            name="ck_ledger_lines_direction",
        ),
        sa.CheckConstraint(
            "amount_pence > 0 AND CAST(amount_pence AS TEXT) NOT LIKE '%.%'",
            name="ck_ledger_lines_amount_positive",
        ),
    )
    op.create_index("ix_ledger_lines_entry_id", "ledger_lines", ["entry_id"])
    op.create_index("ix_ledger_lines_account_id", "ledger_lines", ["account_id"])
    _install_append_only_guards()


def downgrade() -> None:
    op.drop_table("ledger_lines")
    op.drop_table("ledger_entries")
    op.drop_table("ledger_accounts")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS ledger_reject_mutation()")


def _install_append_only_guards() -> None:
    """Reject UPDATE and DELETE. Corrections are new rows, on both dialects."""
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION ledger_reject_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'ledger is append-only';
            END;
            $$;
            """
        )
        for table in _TABLES:
            op.execute(
                f"CREATE TRIGGER {table}_append_only_update "
                f"BEFORE UPDATE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION ledger_reject_mutation()"
            )
            op.execute(
                f"CREATE TRIGGER {table}_append_only_delete "
                f"BEFORE DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION ledger_reject_mutation()"
            )
        return
    if dialect == "sqlite":
        for table in _TABLES:
            op.execute(
                f"CREATE TRIGGER {table}_append_only_update "
                f"BEFORE UPDATE ON {table} "
                f"FOR EACH ROW "
                f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
            )
            op.execute(
                f"CREATE TRIGGER {table}_append_only_delete "
                f"BEFORE DELETE ON {table} "
                f"FOR EACH ROW "
                f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
            )
        return
    raise RuntimeError(f"unsupported database dialect: {dialect}")
