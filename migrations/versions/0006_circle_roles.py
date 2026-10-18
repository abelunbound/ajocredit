"""per-circle roles on circle membership

Revision ID: 0006_circle_roles
Revises: 0005_email_verification
Create Date: 2026-10-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_circle_roles"
down_revision: Union[str, Sequence[str], None] = "0005_email_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("circle_members") as batch:
        batch.add_column(
            sa.Column(
                "role",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'member'"),
            )
        )
        batch.create_check_constraint(
            "ck_circle_members_role",
            "role IN ('admin', 'member')",
        )
    # Creators are the admin of the circle they created. Everyone else stays member.
    op.execute(
        """
        UPDATE circle_members
        SET role = 'admin'
        WHERE EXISTS (
            SELECT 1 FROM circles
            WHERE circles.id = circle_members.circle_id
              AND circles.created_by_user_id = circle_members.user_id
        )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("circle_members") as batch:
        batch.drop_constraint("ck_circle_members_role", type_="check")
        batch.drop_column("role")
