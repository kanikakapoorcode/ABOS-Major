"""
Agent performance profile — updated after every execution and feedback event.
Used by the scheduler to compute routing scores.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.session import Base
from backend.db.models.base import UUIDMixin


class AgentProfile(UUIDMixin, Base):
    __tablename__ = "agent_profiles"

    agent_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Rolling-window performance metrics (used by the scheduler)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    total_executions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_size: Mapped[int] = mapped_column(Integer, nullable=False, default=50)

    last_updated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
