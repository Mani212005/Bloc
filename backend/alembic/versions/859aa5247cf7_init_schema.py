"""init schema

Revision ID: 859aa5247cf7
Revises: 
Create Date: 2026-02-24 19:09:43.867125

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '859aa5247cf7'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    caller_status = postgresql.ENUM(
        "active", "paused", name="caller_status", create_type=False
    )
    lead_assignment_status = postgresql.ENUM(
        "assigned", "unassigned", name="lead_assignment_status", create_type=False
    )

    caller_status.create(op.get_bind(), checkfirst=True)
    lead_assignment_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "callers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("languages", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            caller_status,
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("timestamp_from_sheet", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lead_source", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "unassigned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.UniqueConstraint("phone", "timestamp_from_sheet", name="uq_lead_phone_ts"),
    )

    op.create_table(
        "rr_pointers",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("last_caller_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "caller_states",
        sa.Column(
            "caller_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("callers.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("state", sa.Text(), primary_key=True),
    )

    op.create_table(
        "caller_daily_counters",
        sa.Column(
            "caller_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("callers.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("date", sa.Date(), primary_key=True),
        sa.Column(
            "count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.create_table(
        "lead_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "caller_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("callers.id"),
            nullable=True,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("assignment_reason", sa.Text(), nullable=False),
        sa.Column(
            "status",
            lead_assignment_status,
            nullable=False,
            server_default="assigned",
        ),
    )

    op.create_index(
        "ix_leads_state",
        "leads",
        ["state"],
    )
    op.create_index(
        "ix_leads_created_at",
        "leads",
        ["created_at"],
    )
    op.create_index(
        "ix_lead_assignments_caller_id",
        "lead_assignments",
        ["caller_id"],
    )
    op.create_index(
        "ix_lead_assignments_lead_id",
        "lead_assignments",
        ["lead_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_lead_assignments_lead_id", table_name="lead_assignments")
    op.drop_index("ix_lead_assignments_caller_id", table_name="lead_assignments")
    op.drop_index("ix_leads_created_at", table_name="leads")
    op.drop_index("ix_leads_state", table_name="leads")

    op.drop_table("lead_assignments")
    op.drop_table("caller_daily_counters")
    op.drop_table("caller_states")
    op.drop_table("rr_pointers")
    op.drop_table("leads")
    op.drop_table("callers")

    lead_assignment_status = postgresql.ENUM(
        "assigned", "unassigned", name="lead_assignment_status"
    )
    caller_status = postgresql.ENUM("active", "paused", name="caller_status")

    lead_assignment_status.drop(op.get_bind(), checkfirst=True)
    caller_status.drop(op.get_bind(), checkfirst=True)

