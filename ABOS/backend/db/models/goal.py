import uuid
from typing import Optional

from sqlalchemy import String, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.session import Base
from backend.db.models.base import UUIDMixin, TimestampMixin


class Goal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "goals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    target_departments: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="goals")  # noqa: F821
    workflows: Mapped[list["Workflow"]] = relationship(  # noqa: F821
        "Workflow", back_populates="goal", cascade="all, delete-orphan"
    )
