"""
Feedback model — Level-2 explicit-feedback memory layer.
Stores pgvector embedding of correction text for semantic retrieval.
"""

import uuid
from typing import Optional

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from backend.db.session import Base
from backend.db.models.base import UUIDMixin, TimestampMixin


class Feedback(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "feedback"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rating: Mapped[str] = mapped_column(String(20), nullable=False)
    correction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_agent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # pgvector: 1536-dim embedding of correction text (OpenAI/Gemini embedding size)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(1536), nullable=True)

    execution: Mapped["Execution"] = relationship(  # noqa: F821
        "Execution", back_populates="feedbacks"
    )
