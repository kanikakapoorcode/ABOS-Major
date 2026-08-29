"""
Agent performance profiles — updated after every execution and feedback event.
Used by the scheduler to compute routing scores under the 3-tier evidence hierarchy:
  1. Task-Specific Profile (AgentTaskProfile)
  2. Aggregate Profile (AgentProfile)
  3. Cold-Start Prior (0.41)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.session import Base
from backend.db.models.base import UUIDMixin


class AgentProfile(UUIDMixin, Base):
    """
    Tier-2 Evidence: Aggregate performance metrics across all task types for an agent.
    """
    __tablename__ = "agent_profiles"

    agent_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Rolling-window performance metrics (used by the scheduler)
    # Cold-start defaults represent neutral priors ('no evidence yet', composite score = 0.41)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    avg_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)

    total_executions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_size: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    last_updated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )


class AgentTaskProfile(UUIDMixin, Base):
    """
    Tier-1 Evidence: Fine-grained performance metrics conditioned on (agent_name, department, task_type).
    """
    __tablename__ = "agent_task_profiles"
    __table_args__ = (
        UniqueConstraint("agent_name", "department", "task_type", name="uq_agent_dept_task_profile"),
        Index("ix_agent_dept_task_lookup", "agent_name", "department", "task_type"),
    )

    agent_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    avg_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.2)

    total_executions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_size: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    last_updated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )
