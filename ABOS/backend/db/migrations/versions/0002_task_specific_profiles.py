"""add task-specific profiles and task_type columns

Revision ID: 0002_task_specific_profiles
Revises: 0001_initial_schema
Create Date: 2026-08-29

Tables created:
  agent_task_profiles

Columns added:
  workflow_steps.task_type
  executions.task_type
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers
revision: str = "0002_task_specific_profiles"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── agent_task_profiles ───────────────────────────────────────────────────
    op.create_table(
        "agent_task_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("avg_latency_ms", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default=sa.text("0.2")),
        sa.Column("total_executions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("window_size", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.UniqueConstraint("agent_name", "department", "task_type", name="uq_agent_dept_task_profile"),
    )
    op.create_index("ix_agent_task_profiles_agent_name", "agent_task_profiles", ["agent_name"])
    op.create_index("ix_agent_task_profiles_department", "agent_task_profiles", ["department"])
    op.create_index("ix_agent_task_profiles_task_type", "agent_task_profiles", ["task_type"])
    op.create_index(
        "ix_agent_dept_task_lookup",
        "agent_task_profiles",
        ["agent_name", "department", "task_type"],
    )

    # ── add task_type to workflow_steps ───────────────────────────────────────
    op.add_column("workflow_steps", sa.Column("task_type", sa.String(50), nullable=True))
    op.create_index("ix_workflow_steps_task_type", "workflow_steps", ["task_type"])

    # ── add task_type to executions ───────────────────────────────────────────
    op.add_column("executions", sa.Column("task_type", sa.String(50), nullable=True))
    op.create_index("ix_executions_task_type", "executions", ["task_type"])


def downgrade() -> None:
    op.drop_index("ix_executions_task_type", table_name="executions")
    op.drop_column("executions", "task_type")

    op.drop_index("ix_workflow_steps_task_type", table_name="workflow_steps")
    op.drop_column("workflow_steps", "task_type")

    op.drop_index("ix_agent_task_profiles_task_type", table_name="agent_task_profiles")
    op.drop_index("ix_agent_task_profiles_department", table_name="agent_task_profiles")
    op.drop_index("ix_agent_task_profiles_agent_name", table_name="agent_task_profiles")
    op.drop_table("agent_task_profiles")
