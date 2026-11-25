"""add multilingual summary and compliance fields to workflows

Revision ID: 0003_workflow_summary_and_language
Revises: 0002_task_specific_profiles
Create Date: 2026-11-25

Columns added to workflows:
  detected_language, summary, localised_summary,
  compliance_flags, localised_compliance_flags, error
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0003_workflow_summary_and_language"
down_revision: Union[str, None] = "0002_task_specific_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workflows", sa.Column("detected_language", sa.String(20), nullable=True))
    op.add_column("workflows", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("workflows", sa.Column("localised_summary", sa.Text(), nullable=True))
    op.add_column(
        "workflows",
        sa.Column("compliance_flags", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "workflows",
        sa.Column("localised_compliance_flags", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("workflows", sa.Column("error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("workflows", "error")
    op.drop_column("workflows", "localised_compliance_flags")
    op.drop_column("workflows", "compliance_flags")
    op.drop_column("workflows", "localised_summary")
    op.drop_column("workflows", "summary")
    op.drop_column("workflows", "detected_language")
