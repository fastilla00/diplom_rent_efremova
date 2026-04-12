# EcomProfit Guard — analytics router
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.analytics import AnalyticsOut, PeriodRow, GroupRow
from app.services.analytics_service import get_analytics
from app.routers.auth import require_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/{project_id}", response_model=AnalyticsOut)
async def analytics(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    group_by: str = Query("month", regex="^(month|quarter|year)$"),
):
    res = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    if not res.scalar_one_or_none():
        raise HTTPException(404, "Project not found")
    period_end = period_end or date.today()
    period_start = period_start or (period_end - timedelta(days=365))
    data = await get_analytics(db, project_id, period_start, period_end, group_by)
    return AnalyticsOut(
        by_period=[PeriodRow(**x) for x in data["by_period"]],
        by_project=[GroupRow(**x) for x in data["by_project"]],
        by_client=[GroupRow(**x) for x in data["by_client"]],
        by_specialist=[GroupRow(**x) for x in data["by_specialist"]],
        by_department=[GroupRow(**x) for x in data["by_department"]],
    )
