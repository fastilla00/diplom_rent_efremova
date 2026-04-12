# EcomProfit Guard — costs (from sheet Затраты)
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Date, Numeric, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Cost(Base):
    __tablename__ = "costs"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    counterparty: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cost_date: Mapped[date] = mapped_column(Date, nullable=True)
    category: Mapped[str] = mapped_column(String(255), nullable=True)
    tag: Mapped[str] = mapped_column(String(255), nullable=True)
    contract: Mapped[str] = mapped_column(String(255), nullable=True)
    purpose: Mapped[str] = mapped_column(String(512), nullable=True)
    payment_type: Mapped[str] = mapped_column(String(128), nullable=True)
    payment_deadline: Mapped[date] = mapped_column(Date, nullable=True)
    cost_center: Mapped[str] = mapped_column(String(255), nullable=True)
    sheet_project: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    specialist: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    payment_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=True)
    payment_status: Mapped[str] = mapped_column(String(64), nullable=True)
    cost_month: Mapped[str] = mapped_column(String(32), nullable=True)
    debt: Mapped[str] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
