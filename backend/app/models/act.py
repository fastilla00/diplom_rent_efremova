# EcomProfit Guard — acts (from sheet Акты)
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Date, Numeric, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Act(Base):
    __tablename__ = "acts"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    cfo: Mapped[str] = mapped_column(String(255), nullable=True)
    department: Mapped[str] = mapped_column(String(255), nullable=True)
    sub_department: Mapped[str] = mapped_column(String(255), nullable=True)
    company: Mapped[str] = mapped_column(String(255), nullable=True)
    account_manager: Mapped[str] = mapped_column(String(255), nullable=True)
    client: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    client_legal: Mapped[str] = mapped_column(String(255), nullable=True)
    contract: Mapped[str] = mapped_column(String(255), nullable=True)
    doc_status: Mapped[str] = mapped_column(String(128), nullable=True)
    task: Mapped[str] = mapped_column(String(512), nullable=True)
    pm: Mapped[str] = mapped_column(String(255), nullable=True)
    tl: Mapped[str] = mapped_column(String(255), nullable=True)
    specialist: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    hours: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=True)
    revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=True)
    revenue_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=True)
    payment: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=True)
    payment_vat: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=True)
    invoice_number: Mapped[str] = mapped_column(String(128), nullable=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=True)
    payment_due: Mapped[date] = mapped_column(Date, nullable=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=True)
    payment_status: Mapped[str] = mapped_column(String(64), nullable=True)
    act_number: Mapped[str] = mapped_column(String(128), nullable=True)
    act_date: Mapped[date] = mapped_column(Date, nullable=True)
    act_status: Mapped[str] = mapped_column(String(64), nullable=True)
    shipment_date: Mapped[date] = mapped_column(Date, nullable=True)  # дата отгрузки — по ней считаем когда пришли деньги
    shipment_due: Mapped[date] = mapped_column(Date, nullable=True)
    shipment_debt: Mapped[str] = mapped_column(String(64), nullable=True)
    plan_start: Mapped[date] = mapped_column(Date, nullable=True)
    fact_start: Mapped[date] = mapped_column(Date, nullable=True)
    plan_end: Mapped[date] = mapped_column(Date, nullable=True)
    tracker_link: Mapped[str] = mapped_column(String(512), nullable=True)
    profitability_plan: Mapped[float] = mapped_column(Numeric(8, 2), nullable=True)
    profitability_fact: Mapped[float] = mapped_column(Numeric(8, 2), nullable=True)
    period_month: Mapped[str] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
