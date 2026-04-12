# EcomProfit Guard — specialists and monthly revenue (from sheet TL/Специалисты)
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, ForeignKey, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Specialist(Base):
    __tablename__ = "specialists"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    specialist_type: Mapped[str] = mapped_column(String(64), nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=True)
    total_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SpecialistMonthlyRevenue(Base):
    __tablename__ = "specialist_monthly_revenue"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    specialist_id: Mapped[int] = mapped_column(ForeignKey("specialists.id", ondelete="CASCADE"), nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
