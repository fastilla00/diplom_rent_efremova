# EcomProfit Guard — алерты: низкая рентабельность (по формуле), просроченные оплаты
from datetime import date
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.act import Act
from app.models.cost import Cost
from app.models.alert import Alert
from app.config import get_settings


async def compute_alerts(
    session: AsyncSession,
    project_id: int,
    profitability_threshold_pct: float | None = None,
) -> list[Alert]:
    threshold = profitability_threshold_pct or get_settings().default_profitability_threshold_pct
    today = date.today()
    new_alerts = []

    # 1) Низкая рентабельность по полю profitability_fact в актах (если есть)
    low_q = select(Act.project_name, Act.client, Act.profitability_fact, Act.revenue).where(
        Act.project_id == project_id,
        Act.profitability_fact.isnot(None),
        Act.profitability_fact < threshold,
        Act.revenue.isnot(None),
        Act.revenue > 0,
    ).distinct()
    for row in (await session.execute(low_q)).all():
        new_alerts.append(Alert(
            project_id=project_id,
            alert_type="low_profitability",
            severity="high" if (row.profitability_fact or 0) < threshold / 2 else "medium",
            title=f"Низкая рентабельность: {row.project_name or row.client or 'Проект'}",
            message=f"Фактическая рентабельность {row.profitability_fact:.1f}% ниже порога {threshold}%.",
            recommendation="Проверьте затраты и ставки по проекту.",
            entity_type="project",
            entity_id=row.project_name or row.client,
            value=float(row.profitability_fact or 0),
            threshold=threshold,
        ))

    # 2) Низкая рентабельность по формуле: (выручка - затраты) / выручка по проекту в целом
    total_rev = (await session.execute(
        select(func.coalesce(func.sum(Act.revenue), 0)).where(
            Act.project_id == project_id,
            Act.revenue.isnot(None),
            Act.revenue > 0,
        )
    )).scalar() or Decimal("0")
    total_cost = (await session.execute(
        select(func.coalesce(func.sum(Cost.amount), 0)).where(Cost.project_id == project_id)
    )).scalar() or Decimal("0")
    if total_rev > 0:
        pct = float((total_rev - total_cost) / total_rev * 100)
        if pct < threshold:
            new_alerts.append(Alert(
                project_id=project_id,
                alert_type="low_profitability",
                severity="high" if pct < threshold / 2 else "medium",
                title="Низкая рентабельность по проекту (расчёт по формуле)",
                message=f"Рентабельность {pct:.1f}% (выручка − затраты) ниже порога {threshold}%.",
                recommendation="Проверьте затраты и выручку в актах и затратах.",
                entity_type="project",
                entity_id=None,
                value=pct,
                threshold=threshold,
            ))

    # 3) Просроченные оплаты: дата оплаты не заполнена, ожидание оплаты в прошлом
    overdue_q = select(Act).where(
        Act.project_id == project_id,
        Act.payment_due.isnot(None),
        Act.payment_due < today,
        Act.payment_date.is_(None),
    ).limit(50)
    for act in (await session.execute(overdue_q)).scalars().all():
        new_alerts.append(Alert(
            project_id=project_id,
            alert_type="overdue_payment",
            severity="high" if (today - act.payment_due).days > 30 else "medium",
            title=f"Просроченная оплата: {act.client} — {act.act_number or 'акт'}",
            message=f"Ожидаемая дата оплаты {act.payment_due}; сумма {act.revenue or 0} руб.",
            recommendation="Связаться с клиентом, уточнить срок оплаты.",
            entity_type="act",
            entity_id=act.act_number or str(act.id),
            value=float(act.revenue or 0),
            threshold=0,
        ))

    for a in new_alerts:
        session.add(a)
    await session.flush()
    return new_alerts


async def list_alerts(
    session: AsyncSession,
    project_id: int,
    unread_only: bool = False,
    limit: int = 100,
) -> list[Alert]:
    q = select(Alert).where(Alert.project_id == project_id).order_by(Alert.created_at.desc()).limit(limit)
    if unread_only:
        q = q.where(Alert.read_at.is_(None))
    res = await session.execute(q)
    return list(res.scalars().all())
