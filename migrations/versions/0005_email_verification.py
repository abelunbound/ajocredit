"""email verification and circle membership gate

Revision ID: 0005_email_verification
Revises: 0004_password_reset
Create Date: 2026-10-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_email_verification"
down_revision: Union[str, Sequence[str], None] = "0004_password_reset"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_email_verification_tokens_user_id",
        ),
        sa.UniqueConstraint("token_hash", name="uq_email_verification_tokens_token_hash"),
    )
    op.create_index("ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"])
    op.create_table(
        "circles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_circles_created_by_user_id",
        ),
    )
    op.create_index("ix_circles_created_by_user_id", "circles", ["created_by_user_id"])
    op.create_table(
        "circle_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("circle_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["circle_id"], ["circles.id"], name="fk_circle_members_circle_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_circle_members_user_id"),
        sa.UniqueConstraint("circle_id", "user_id", name="uq_circle_members_circle_user"),
    )
    op.create_index("ix_circle_members_circle_id", "circle_members", ["circle_id"])
    op.create_index("ix_circle_members_user_id", "circle_members", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_circle_members_user_id", table_name="circle_members")
    op.drop_index("ix_circle_members_circle_id", table_name="circle_members")
    op.drop_table("circle_members")
    op.drop_index("ix_circles_created_by_user_id", table_name="circles")
    op.drop_table("circles")
    op.drop_index("ix_email_verification_tokens_user_id", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_verified_at")
