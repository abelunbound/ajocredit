"""append-only audit log and platform admin role

Revision ID: 0008_audit_log
Revises: 0007_auth_rate_limits
Create Date: 2026-10-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_audit_log"
down_revision: Union[str, Sequence[str], None] = "0007_auth_rate_limits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("platform_role", sa.String(length=32), nullable=True))
        batch.create_check_constraint(
            "ck_users_platform_role",
            "platform_role IS NULL OR platform_role = 'platform_admin'",
        )
    op.create_table(
        "audit_chain_lock",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("guard", sa.Integer(), nullable=False),
    )
    op.execute("INSERT INTO audit_chain_lock (id, guard) VALUES (1, 0)")
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("circle_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("email_hash", sa.String(length=64), nullable=True),
        sa.Column("before_values", sa.Text(), nullable=True),
        sa.Column("after_values", sa.Text(), nullable=True),
        sa.Column("prev_hash", sa.String(length=64), nullable=True),
        sa.Column("entry_hash", sa.String(length=64), nullable=False),
        sa.Column("canonical", sa.Text(), nullable=False),
        sa.UniqueConstraint("entry_hash", name="uq_audit_log_entry_hash"),
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_actor_user_id", "audit_log", ["actor_user_id"])
    op.create_index("ix_audit_log_circle_id", "audit_log", ["circle_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_target_user_id", "audit_log", ["target_user_id"])
    op.create_index("ix_audit_log_email_hash", "audit_log", ["email_hash"])
    _install_append_only_guards()


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("audit_chain_lock")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS audit_log_reject_mutation()")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_platform_role", type_="check")
        batch.drop_column("platform_role")


def _install_append_only_guards() -> None:
    """Reject UPDATE and DELETE on audit_log. The application role cannot mutate it."""
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION audit_log_reject_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'audit_log is append-only';
            END;
            $$;
            """
        )
        op.execute(
            "CREATE TRIGGER audit_log_append_only_update "
            "BEFORE UPDATE ON audit_log "
            "FOR EACH ROW EXECUTE FUNCTION audit_log_reject_mutation()"
        )
        op.execute(
            "CREATE TRIGGER audit_log_append_only_delete "
            "BEFORE DELETE ON audit_log "
            "FOR EACH ROW EXECUTE FUNCTION audit_log_reject_mutation()"
        )
        return
    if dialect == "sqlite":
        op.execute(
            "CREATE TRIGGER audit_log_append_only_update "
            "BEFORE UPDATE ON audit_log "
            "FOR EACH ROW "
            "BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END"
        )
        op.execute(
            "CREATE TRIGGER audit_log_append_only_delete "
            "BEFORE DELETE ON audit_log "
            "FOR EACH ROW "
            "BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END"
        )
        return
    raise RuntimeError(f"unsupported database dialect: {dialect}")
