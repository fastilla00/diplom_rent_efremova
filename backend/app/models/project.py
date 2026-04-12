# EcomProfit Guard — project model
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    integration: Mapped["ProjectIntegration"] = relationship("ProjectIntegration", back_populates="project", uselist=False, cascade="all, delete-orphan")


class ProjectIntegration(Base):
    __tablename__ = "project_integrations"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    spreadsheet_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sheet_acts: Mapped[str] = mapped_column(String(128), default="Акты")
    sheet_costs: Mapped[str] = mapped_column(String(128), default="Затраты")
    sheet_specialists: Mapped[str] = mapped_column(String(128), default="TL")
    sheet_metrics: Mapped[str] = mapped_column(String(128), default="Метрики")
    last_sync_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    project: Mapped["Project"] = relationship("Project", back_populates="integration")
