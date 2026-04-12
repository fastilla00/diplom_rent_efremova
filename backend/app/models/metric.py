# EcomProfit Guard — monthly metrics (sheet Метрики or aggregated)
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, Numeric, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Metric(Base):
    __tablename__ = "metrics"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=True)
    costs: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=True)
    rent: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=True)
    sales_count: Mapped[int] = mapped_column(Integer, nullable=True)
    conversion: Mapped[float] = mapped_column(Numeric(8, 4), nullable=True)
    profitability_pct: Mapped[float] = mapped_column(Numeric(8, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("project_id", "year", "month", name="uq_metrics_project_year_month"),)
