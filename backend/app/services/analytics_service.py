# EcomProfit Guard — analytics aggregations
# Выручка по актам относим к периоду по дате отгрузки (деньги по отгрузке), иначе по дате акта.
from datetime import date
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.act import Act
from app.models.cost import Cost

_revenue_date = func.coalesce(Act.shipment_date, Act.act_date)


async def get_analytics(
    session: AsyncSession,
    project_id: int,
    period_start: date,
    period_end: date,
    group_by: str = "month",
) -> dict:
    by_period = await _by_period(session, project_id, period_start, period_end, group_by)
    by_project = await _by_group(session, project_id, period_start, period_end, Act.project_name)
    by_client = await _by_group(session, project_id, period_start, period_end, Act.client)
    by_specialist = await _by_group(session, project_id, period_start, period_end, Act.specialist)
    by_department = await _by_group(session, project_id, period_start, period_end, Act.department)
    return {
        "by_period": by_period,
        "by_project": by_project,
        "by_client": by_client,
        "by_specialist": by_specialist,
        "by_department": by_department,
    }


def _period_key(d: date, group_by: str) -> str:
    if group_by == "year":
        return str(d.year)
    if group_by == "quarter":
        q = (d.month - 1) // 3 + 1
        return f"{d.year}-Q{q}"
    return f"{d.year}-{d.month:02d}"


async def _by_period(
    session: AsyncSession,
    project_id: int,
    period_start: date,
    period_end: date,
    group_by: str,
) -> list[dict]:
    rev_q = select(_revenue_date.label("revenue_date"), Act.revenue).where(
        Act.project_id == project_id,
        _revenue_date.isnot(None),
        _revenue_date >= period_start,
        _revenue_date <= period_end,
        Act.revenue.isnot(None),
    )
    rev_res = await session.execute(rev_q)
    rows = rev_res.all()
    by_key: dict[str, Decimal] = {}
    for r in rows:
        if not r.revenue_date:
            continue
        k = _period_key(r.revenue_date, group_by)
        by_key[k] = by_key.get(k, Decimal("0")) + (r.revenue or Decimal("0"))
    cost_q = select(Cost.cost_date, Cost.amount).where(
        Cost.project_id == project_id,
        Cost.cost_date.isnot(None),
        Cost.cost_date >= period_start,
        Cost.cost_date <= period_end,
    )
    cost_res = await session.execute(cost_q)
    cost_by_key: dict[str, Decimal] = {}
    for r in cost_res.all():
        if not r.cost_date:
            continue
        k = _period_key(r.cost_date, group_by)
        cost_by_key[k] = cost_by_key.get(k, Decimal("0")) + (r.amount or Decimal("0"))

    # Если по периоду пусто — берём все акты/затраты без фильтра по дате
    if not by_key:
        rev_all = await session.execute(
            select(_revenue_date.label("revenue_date"), Act.revenue).where(
                Act.project_id == project_id,
                Act.revenue.isnot(None),
            )
        )
        for r in rev_all.all():
            if r.revenue_date:
                k = _period_key(r.revenue_date, group_by)
                by_key[k] = by_key.get(k, Decimal("0")) + (r.revenue or Decimal("0"))
        if not by_key:
            rev_sum = await session.execute(
                select(func.coalesce(func.sum(Act.revenue), 0)).where(
                    Act.project_id == project_id,
                    Act.revenue.isnot(None),
                )
            )
            total_r = rev_sum.scalar() or Decimal("0")
            if total_r > 0:
                by_key["Все"] = total_r
    if not cost_by_key:
        cost_all = await session.execute(
            select(Cost.cost_date, Cost.amount).where(Cost.project_id == project_id)
        )
        for r in cost_all.all():
            if r.cost_date:
                k = _period_key(r.cost_date, group_by)
                cost_by_key[k] = cost_by_key.get(k, Decimal("0")) + (r.amount or Decimal("0"))
        if not cost_by_key:
            cost_sum = await session.execute(
                select(func.coalesce(func.sum(Cost.amount), 0)).where(Cost.project_id == project_id)
            )
            total_c = cost_sum.scalar() or Decimal("0")
            if total_c > 0:
                cost_by_key["Все"] = total_c

    total_rev = sum(by_key.values())
    total_cost = sum(cost_by_key.values())
    out = []
    for period in sorted(by_key.keys()):
        rev = by_key[period]
        cost = (rev / total_rev * total_cost) if total_rev and total_rev > 0 else cost_by_key.get(period, Decimal("0"))
        profit = rev - cost
        pct = float(profit / rev * 100) if rev else None
        out.append({"period": period, "revenue": rev, "costs": cost, "profit": profit, "profitability_pct": pct, "count": None})
    return out


async def _by_group(
    session: AsyncSession,
    project_id: int,
    period_start: date,
    period_end: date,
    group_col,
) -> list[dict]:
    rev_q = (
        select(group_col.label("name"), func.sum(Act.revenue).label("revenue"), func.count(Act.id).label("cnt"))
        .where(
            Act.project_id == project_id,
            _revenue_date >= period_start,
            _revenue_date <= period_end,
            Act.revenue.isnot(None),
            group_col.isnot(None),
            group_col != "",
        )
        .group_by(group_col)
        .order_by(func.sum(Act.revenue).desc())
        .limit(50)
    )
    res = await session.execute(rev_q)
    rows = res.all()
    # Если с фильтром по дате пусто — считаем без фильтра
    if not rows:
        rev_q = (
            select(group_col.label("name"), func.sum(Act.revenue).label("revenue"), func.count(Act.id).label("cnt"))
            .where(
                Act.project_id == project_id,
                Act.revenue.isnot(None),
                group_col.isnot(None),
                group_col != "",
            )
            .group_by(group_col)
            .order_by(func.sum(Act.revenue).desc())
            .limit(50)
        )
        res = await session.execute(rev_q)
        rows = res.all()
    total_rev = sum((r.revenue or Decimal("0")) for r in rows)
    cost_q = select(func.coalesce(func.sum(Cost.amount), 0)).where(
        Cost.project_id == project_id,
        Cost.cost_date >= period_start,
        Cost.cost_date <= period_end,
    )
    total_cost = (await session.execute(cost_q)).scalar() or Decimal("0")
    if total_cost == 0:
        total_cost = (await session.execute(select(func.coalesce(func.sum(Cost.amount), 0)).where(Cost.project_id == project_id))).scalar() or Decimal("0")
    out = []
    for r in rows:
        rev = r.revenue or Decimal("0")
        cost = (rev / total_rev * total_cost) if total_rev else Decimal("0")
        profit = rev - cost
        pct = float(profit / rev * 100) if rev else None
        out.append({
            "name": r.name or "—",
            "revenue": rev,
            "costs": cost,
            "profit": profit,
            "profitability_pct": pct,
            "count": r.cnt,
        })
    return out
