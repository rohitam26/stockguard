import uuid
from enum import Enum
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
from stockguard.models.base import Base, TimestampMixin


class OutboxStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class OutboxMessage(Base, TimestampMixin):
    __tablename__ = "outbox_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    headers: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[OutboxStatus] = mapped_column(
        SQLEnum(OutboxStatus, native_enum=False, length=20),
        default=OutboxStatus.PENDING,
        nullable=False,
        index=True,
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
