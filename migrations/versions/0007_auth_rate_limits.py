"""auth rate-limit buckets and account lockout

Revision ID: 0007_auth_rate_limits
Revises: 0006_circle_roles
Create Date: 2026-10-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_auth_rate_limits"
down_revision: Union[str, Sequence[str], None] = "0006_circle_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_rate_buckets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=64), nullable=False),
        sa.Column("window_started", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.UniqueConstraint("action", "scope", "subject", name="uq_auth_rate_buckets_key"),
    )
    op.create_table(
        "auth_account_guards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=64), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified_level", sa.Integer(), nullable=False),
        sa.UniqueConstraint("action", "subject", name="uq_auth_account_guards_key"),
    )


def downgrade() -> None:
    op.drop_table("auth_account_guards")
    op.drop_table("auth_rate_buckets")
