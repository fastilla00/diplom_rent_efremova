# EcomProfit Guard — dashboard aggregation
# Акты (Act) = ДОХОДЫ, выручка. Затраты (Cost) = РАСХОДЫ, траты.
# Выручку относим к периоду по дате отгрузки (деньги получили по отгрузке), иначе по дате акта.
# При наличии эталонной выручки из листа TL/Специалисты (строки 66, 139, 160) используем её.
from datetime import date
from decimal import Decimal
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.act import Act
from app.models.cost import Cost
from app.models.metric import Metric

# Дата, по которой считаем приход денег по акту: сначала дата отгрузки, иначе дата акта
_revenue_date = func.coalesce(Act.shipment_date, Act.act_date)


def _months_in_period(start: date, end: date) -> list[tuple[int, int]]:
    """Список (year, month) для всех месяцев в [start, end]."""
    out = []
    y, m = start.year, start.month
    y_end, m_end = end.year, end.month
    while (y, m) <= (y_end, m_end):
        out.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


async def get_dashboard(
    session: AsyncSession,
    project_id: int,
    period_start: date,
    period_end: date,
) -> dict[str, object]:
    """Агрегирует выручку, затраты, прибыль и топы по проекту за период.

    Выручка: сначала сумма по `Metric` за месяцы периода (эталон TL), иначе по актам
    с датой `coalesce(shipment_date, act_date)`. Если по датам пусто — показ по всему проекту.

    Returns:
        Словарь с ключами `summary`, `top_projects`, `top_specialists`, `by_department`,
        `period_start`, `period_end` (даты в ISO).
    """
    # Выручка: приоритет — эталон из Metric (TL/Специалисты строки 66, 139, 160), иначе сумма по актам по дате отгрузки
    months = _months_in_period(period_start, period_end)
    revenue_from_metric = Decimal("0")
    if months:
        metric_rev_q = select(func.coalesce(func.sum(Metric.revenue), 0)).where(
            Metric.project_id == project_id,
            Metric.revenue.isnot(None),
            Metric.revenue > 0,
            or_(*(and_(Metric.year == ym[0], Metric.month == ym[1]) for ym in months)),
        )
        metric_res = await session.execute(metric_rev_q)
        revenue_from_metric = metric_res.scalar() or Decimal("0")
    if revenue_from_metric > 0:
        revenue = revenue_from_metric
    else:
        rev_q = select(func.coalesce(func.sum(Act.revenue), 0)).where(
            Act.project_id == project_id,
            Act.revenue.isnot(None),
            Act.revenue > 0,
            _revenue_date >= period_start,
            _revenue_date <= period_end,
        )
        rev_res = await session.execute(rev_q)
        revenue = rev_res.scalar() or Decimal("0")
    # Затраты = сумма из листа ЗАТРАТЫ (расходы, уходящие деньги)
    cost_q = select(func.coalesce(func.sum(Cost.amount), 0)).where(
        Cost.project_id == project_id,
        Cost.cost_date >= period_start,
        Cost.cost_date <= period_end,
    )
    cost_res = await session.execute(cost_q)
    costs = cost_res.scalar() or Decimal("0")
    # Если по периоду пусто — показываем все данные проекта (без фильтра по дате)
    use_date_filter = revenue > 0 or costs > 0
    if not use_date_filter:
        rev_all = await session.execute(
            select(func.coalesce(func.sum(Act.revenue), 0)).where(
                Act.project_id == project_id,
                Act.revenue.isnot(None),
                Act.revenue > 0,
            )
        )
        cost_all = await session.execute(
            select(func.coalesce(func.sum(Cost.amount), 0)).where(Cost.project_id == project_id)
        )
        revenue = rev_all.scalar() or Decimal("0")
        costs = cost_all.scalar() or Decimal("0")

    profit = revenue - costs
    profitability_pct = float(profit / revenue * 100) if revenue else None

    # Клиенты и специалисты — по тем же правилам (с датой или все)
    clients_q = select(func.count(func.distinct(Act.client))).where(
        Act.project_id == project_id,
        Act.client.isnot(None),
        Act.client != "",
        Act.revenue.isnot(None),
    )
    if use_date_filter:
        clients_q = clients_q.where(_revenue_date >= period_start, _revenue_date <= period_end)
    unique_clients = (await session.execute(clients_q)).scalar() or 0

    spec_q = select(func.count(func.distinct(Act.specialist))).where(
        Act.project_id == project_id,
        Act.specialist.isnot(None),
        Act.specialist != "",
        Act.revenue.isnot(None),
    )
    if use_date_filter:
        spec_q = spec_q.where(_revenue_date >= period_start, _revenue_date <= period_end)
    unique_specialists = (await session.execute(spec_q)).scalar() or 0

    top_projects_q = (
        select(Act.project_name, func.sum(Act.revenue).label("s"))
        .where(
            Act.project_id == project_id,
            Act.revenue.isnot(None),
            Act.revenue > 0,
            Act.project_name.isnot(None),
            Act.project_name != "",
        )
        .group_by(Act.project_name)
        .order_by(func.sum(Act.revenue).desc())
        .limit(10)
    )
    if use_date_filter:
        top_projects_q = top_projects_q.where(
            _revenue_date >= period_start,
            _revenue_date <= period_end,
        )
    top_projects = [
        {"name": r.project_name or "—", "value": r.s, "count": None}
        for r in (await session.execute(top_projects_q)).all()
    ]

    top_spec_q = (
        select(Act.specialist, func.sum(Act.revenue).label("s"))
        .where(
            Act.project_id == project_id,
            Act.revenue.isnot(None),
            Act.revenue > 0,
            Act.specialist.isnot(None),
            Act.specialist != "",
        )
        .group_by(Act.specialist)
        .order_by(func.sum(Act.revenue).desc())
        .limit(10)
    )
    if use_date_filter:
        top_spec_q = top_spec_q.where(
            _revenue_date >= period_start,
            _revenue_date <= period_end,
        )
    top_specialists = [
        {"name": r.specialist or "—", "value": r.s, "count": None}
        for r in (await session.execute(top_spec_q)).all()
    ]

    dept_q = (
        select(Act.department, func.sum(Act.revenue).label("s"))
        .where(
            Act.project_id == project_id,
            Act.revenue.isnot(None),
            Act.revenue > 0,
            Act.department.isnot(None),
            Act.department != "",
        )
        .group_by(Act.department)
        .order_by(func.sum(Act.revenue).desc())
        .limit(10)
    )
    if use_date_filter:
        dept_q = dept_q.where(
            _revenue_date >= period_start,
            _revenue_date <= period_end,
        )
    by_department = [
        {"name": r.department or "—", "value": r.s, "count": None}
        for r in (await session.execute(dept_q)).all()
    ]

    return {
        "summary": {
            "revenue": revenue,
            "costs": costs,
            "profit": profit,
            "profitability_pct": profitability_pct,
            "unique_clients": unique_clients,
            "unique_specialists": unique_specialists,
        },
        "top_projects": top_projects,
        "top_specialists": top_specialists,
        "by_department": by_department,
        "period_start": period_start.isoformat() if period_start else "",
        "period_end": period_end.isoformat() if period_end else "",
    }
