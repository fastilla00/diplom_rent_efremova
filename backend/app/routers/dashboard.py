# EcomProfit Guard — dashboard router
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardOut, DashboardSummary, TopItem
from app.services.dashboard_service import get_dashboard
from app.routers.auth import require_user
from app.core.deps import SessionDep

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/{project_id}", response_model=DashboardOut)
async def dashboard(
    project_id: int,
    db: SessionDep,
    user: User = Depends(require_user),
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
):
    from fastapi import HTTPException
    from sqlalchemy import select
    from app.models.project import Project
    res = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    if not res.scalar_one_or_none():
        raise HTTPException(404, "Project not found")
    if not period_start:
        period_end = period_end or date.today()
        period_start = period_end - timedelta(days=365)
    if not period_end:
        period_end = date.today()
    data = await get_dashboard(db, project_id, period_start, period_end)
    return DashboardOut(
        summary=DashboardSummary(**data["summary"]),
        top_projects=[TopItem(**x) for x in data["top_projects"]],
        top_specialists=[TopItem(**x) for x in data["top_specialists"]],
        by_department=[TopItem(**x) for x in data["by_department"]],
        period_start=data["period_start"],
        period_end=data["period_end"],
    )
