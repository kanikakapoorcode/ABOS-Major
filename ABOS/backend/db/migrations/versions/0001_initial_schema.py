"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-16

Tables created:
  users, goals, workflows, workflow_steps,
  executions, agent_profiles, feedback

Also includes:
  - pgvector extension (required before feedback table)
  - token_cost column on executions (logged, not used in scoring — SOURCE_OF_TRUTH §11)
  - all indexes matching the ORM model definitions
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

# revision identifiers
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ── pgvector extension ────────────────────────────────────────────────────
    # Must exist before the feedback table which uses Vector(1536).
    # The Docker postgres-init script also runs this, but we do it here too
    # so plain `alembic upgrade head` works without Docker.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── goals ─────────────────────────────────────────────────────────────────
    op.create_table(
        "goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("target_departments", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("context", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"])
    op.create_index("ix_goals_status", "goals", ["status"])

    # ── workflows ─────────────────────────────────────────────────────────────
    op.create_table(
        "workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("total_steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_steps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_latency_ms", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_workflows_goal_id", "workflows", ["goal_id"])
    op.create_index("ix_workflows_user_id", "workflows", ["user_id"])
    op.create_index("ix_workflows_status", "workflows", ["status"])

    # ── workflow_steps ────────────────────────────────────────────────────────
    op.create_table(
        "workflow_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("assigned_department", sa.String(50), nullable=False),
        sa.Column("assigned_agent", sa.String(100), nullable=False),
        sa.Column("input_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("output_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_workflow_steps_workflow_id", "workflow_steps", ["workflow_id"])

    # ── executions ────────────────────────────────────────────────────────────
    op.create_table(
        "executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("workflow_step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("input_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("output_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("scheduler_score", sa.Float(), nullable=True),
        # token_cost: logged for future analysis, NOT used in scheduling (SOURCE_OF_TRUTH §11)
        sa.Column("token_cost", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workflow_step_id"], ["workflow_steps.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_executions_workflow_step_id", "executions", ["workflow_step_id"])
    op.create_index("ix_executions_agent_name", "executions", ["agent_name"])
    op.create_index("ix_executions_department", "executions", ["department"])
    op.create_index("ix_executions_status", "executions", ["status"])

    # ── agent_profiles ────────────────────────────────────────────────────────
    op.create_table(
        "agent_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("avg_latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("total_executions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_size", sa.Integer(), nullable=False, server_default="50"),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    op.create_index("ix_agent_profiles_agent_name", "agent_profiles", ["agent_name"], unique=True)
    op.create_index("ix_agent_profiles_department", "agent_profiles", ["department"])

    # Seed initial agent profiles with cold-start values
    # (SOURCE_OF_TRUTH §4 — cold start: sr=1.0, lat=0.0, conf=1.0)
    op.execute("""
        INSERT INTO agent_profiles (id, agent_name, department, success_rate, avg_latency_ms, confidence_score, total_executions, window_size)
        VALUES
            (gen_random_uuid(), 'sales_agent',    'sales',    1.0, 0.0, 1.0, 0, 50),
            (gen_random_uuid(), 'support_agent',  'support',  1.0, 0.0, 1.0, 0, 50),
            (gen_random_uuid(), 'research_agent', 'research', 1.0, 0.0, 1.0, 0, 50)
    """)

    # ── feedback ──────────────────────────────────────────────────────────────
    # Created last because it references executions and uses the vector type.
    # We use raw SQL for the full table so the vector(1536) column is handled
    # correctly without depending on pgvector's SQLAlchemy type at migration time.
    op.execute("""
        CREATE TABLE feedback (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
            rating       VARCHAR(20) NOT NULL,
            correction   TEXT,
            suggested_agent VARCHAR(100),
            embedding    vector(1536),
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_execution_id", "feedback", ["execution_id"])

    # IVFFlat index for fast approximate nearest-neighbour search on embeddings
    # lists=100 is appropriate for up to ~1M vectors; adjust if dataset grows
    op.execute("""
        CREATE INDEX ix_feedback_embedding_ivfflat
        ON feedback
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_feedback_embedding_ivfflat")
    op.drop_table("feedback")
    op.drop_table("agent_profiles")
    op.drop_table("executions")
    op.drop_table("workflow_steps")
    op.drop_table("workflows")
    op.drop_table("goals")
    op.drop_table("users")
    # Leave the vector extension — other things may use it
