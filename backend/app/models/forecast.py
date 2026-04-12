# EcomProfit Guard — forecast scenarios and runs
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ForecastScenario(Base):
    __tablename__ = "forecast_scenarios"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    horizon_months: Mapped[int] = mapped_column(Integer, nullable=False)
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ForecastRun(Base):
    __tablename__ = "forecast_runs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("forecast_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    forecast_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    predictions: Mapped[str] = mapped_column(Text, nullable=True)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
