# EcomProfit Guard — alerts router
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.alert import AlertOut
from app.services.alerts_service import compute_alerts, list_alerts
from app.routers.auth import require_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/{project_id}", response_model=list[AlertOut])
async def get_alerts(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    unread_only: bool = Query(False),
    limit: int = Query(100, le=200),
) -> list[AlertOut]:
    """Список алертов проекта с пагинацией по `limit`."""
    res = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    if not res.scalar_one_or_none():
        raise HTTPException(404, "Project not found")
    alerts = await list_alerts(db, project_id, unread_only=unread_only, limit=limit)
    return [AlertOut.model_validate(a) for a in alerts]


@router.post("/{project_id}/compute")
async def run_compute_alerts(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    threshold_pct: float | None = Query(None),
) -> dict[str, int]:
    """Пересчитывает алерты по данным проекта и сохраняет новые записи в БД."""
    res = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    if not res.scalar_one_or_none():
        raise HTTPException(404, "Project not found")
    new_alerts = await compute_alerts(db, project_id, profitability_threshold_pct=threshold_pct)
    return {"computed": len(new_alerts)}
