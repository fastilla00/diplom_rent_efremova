# EcomProfit Guard — projects router
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.project import Project, ProjectIntegration
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectOut, ProjectIntegrationOut
from app.core.utils import spreadsheet_id_from_url
from app.routers.auth import require_user
from app.config import get_settings
from app.services.static_project import ensure_static_project_for_user

router = APIRouter(prefix="/projects", tags=["projects"])


def _forbid_if_static() -> None:
    """Запрещает изменение проектов, если включён режим одной таблицы из `.env`."""
    if get_settings().static_project_enabled:
        raise HTTPException(
            403,
            "Редактирование проектов отключено: задана фиксированная Google Таблица на сервере.",
        )


def _integration_to_out(i: ProjectIntegration) -> ProjectIntegrationOut:
    """Преобразует ORM-интеграцию в схему ответа API."""
    return ProjectIntegrationOut(
        spreadsheet_id=i.spreadsheet_id,
        sheet_acts=i.sheet_acts,
        sheet_costs=i.sheet_costs,
        sheet_specialists=i.sheet_specialists,
        sheet_metrics=i.sheet_metrics,
        last_sync_at=i.last_sync_at,
    )


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> list[ProjectOut]:
    """Список проектов текущего пользователя (в статическом режиме — автосоздание проекта)."""
    if get_settings().static_project_enabled:
        await ensure_static_project_for_user(db, user)
    res = await db.execute(
        select(Project).where(Project.user_id == user.id).order_by(Project.id).options(selectinload(Project.integration))
    )
    projects = res.scalars().all()
    out = []
    for p in projects:
        rec = ProjectOut(id=p.id, name=p.name, created_at=p.created_at, integration=None)
        if p.integration:
            rec.integration = _integration_to_out(p.integration)
        out.append(rec)
    return out


@router.post("", response_model=ProjectOut)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> ProjectOut:
    """Создаёт проект и опционально привязку к Google Таблице (403 в статическом режиме)."""
    _forbid_if_static()
    project = Project(name=body.name, user_id=user.id)
    db.add(project)
    await db.flush()
    await db.refresh(project)
    if body.integration:
        sid = spreadsheet_id_from_url(body.integration.spreadsheet_url)
        if not sid:
            raise HTTPException(400, "Invalid spreadsheet URL")
        integration = ProjectIntegration(
            project_id=project.id,
            spreadsheet_id=sid,
            sheet_acts=body.integration.sheet_acts,
            sheet_costs=body.integration.sheet_costs,
            sheet_specialists=body.integration.sheet_specialists,
            sheet_metrics=body.integration.sheet_metrics,
        )
        db.add(integration)
        await db.flush()
        rec = ProjectOut(id=project.id, name=project.name, created_at=project.created_at, integration=_integration_to_out(integration))
    else:
        rec = ProjectOut(id=project.id, name=project.name, created_at=project.created_at, integration=None)
    return rec


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> ProjectOut:
    """Возвращает один проект пользователя по id."""
    res = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id).options(selectinload(Project.integration))
    )
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    rec = ProjectOut(id=project.id, name=project.name, created_at=project.created_at, integration=None)
    if project.integration:
        rec.integration = _integration_to_out(project.integration)
    return rec


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> ProjectOut:
    """Обновляет имя проекта и/или параметры интеграции с таблицей."""
    _forbid_if_static()
    res = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    if body.name is not None:
        project.name = body.name
    if body.integration is not None:
        sid = spreadsheet_id_from_url(body.integration.spreadsheet_url)
        if not sid:
            raise HTTPException(400, "Invalid spreadsheet URL")
        res2 = await db.execute(select(ProjectIntegration).where(ProjectIntegration.project_id == project_id))
        integration = res2.scalar_one_or_none()
        if integration:
            integration.spreadsheet_id = sid
            integration.sheet_acts = body.integration.sheet_acts
            integration.sheet_costs = body.integration.sheet_costs
            integration.sheet_specialists = body.integration.sheet_specialists
            integration.sheet_metrics = body.integration.sheet_metrics
        else:
            integration = ProjectIntegration(
                project_id=project.id,
                spreadsheet_id=sid,
                sheet_acts=body.integration.sheet_acts,
                sheet_costs=body.integration.sheet_costs,
                sheet_specialists=body.integration.sheet_specialists,
                sheet_metrics=body.integration.sheet_metrics,
            )
            db.add(integration)
    await db.flush()
    res = await db.execute(select(Project).where(Project.id == project_id).options(selectinload(Project.integration)))
    project = res.scalar_one()
    rec = ProjectOut(id=project.id, name=project.name, created_at=project.created_at, integration=None)
    if project.integration:
        rec.integration = _integration_to_out(project.integration)
    return rec


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    """Удаляет проект пользователя (403 в статическом режиме)."""
    _forbid_if_static()
    res = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    await db.delete(project)
    await db.flush()
    return None
