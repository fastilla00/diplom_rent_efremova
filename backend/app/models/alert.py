# EcomProfit Guard — alerts
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str] = mapped_column(String(255), nullable=True)
    value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    threshold: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
