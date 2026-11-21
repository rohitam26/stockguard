from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from stockguard.models.base import Base, utc_now


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    # Compound or unique message id + consumer name
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    consumer_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
