# EcomProfit Guard — sync router
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from google.oauth2.credentials import Credentials
from app.database import get_db
from app.models.project import Project, ProjectIntegration
from app.models.user import User
from app.services.sheets_sync import sync_project_sheets
from app.services.google_auth import credentials_for_user
from app.routers.auth import require_user

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/{project_id}")
async def run_sync(
  project_id: int,
  db: AsyncSession = Depends(get_db),
  user: User = Depends(require_user),
):
    res = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    res2 = await db.execute(select(ProjectIntegration).where(ProjectIntegration.project_id == project_id))
    integration = res2.scalar_one_or_none()
    if not integration:
        raise HTTPException(400, "Project has no Google Sheets integration")
    if not user.access_token:
        raise HTTPException(400, "Re-authenticate with Google to sync")
    creds = credentials_for_user(
        user.access_token,
        user.refresh_token,
        user.token_expires_at,
    )
    try:
        last_sync = await sync_project_sheets(db, project_id, creds)
        return {"ok": True, "last_sync_at": last_sync.isoformat()}
    except Exception as e:
        raise HTTPException(502, f"Sync failed: {e}")
