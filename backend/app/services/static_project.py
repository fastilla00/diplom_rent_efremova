# Один зафиксированный проект на пользователя (таблица и листы из настроек)
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.project import Project, ProjectIntegration
from app.models.user import User


async def ensure_static_project_for_user(db: AsyncSession, user: User) -> Project | None:
    """При `static_project_enabled` создаёт или обновляет единственный проект пользователя из настроек `.env`.

    Returns:
        Актуальный `Project` или None, если режим статического проекта выключен или не задан `spreadsheet_id`.
    """
    s = get_settings()
    if not s.static_project_enabled:
        return None
    sid = (s.static_spreadsheet_id or "").strip()
    if not sid:
        return None

    res = await db.execute(
        select(Project)
        .join(ProjectIntegration, ProjectIntegration.project_id == Project.id)
        .where(Project.user_id == user.id, ProjectIntegration.spreadsheet_id == sid)
        .options(selectinload(Project.integration))
        .limit(1)
    )
    project = res.scalars().first()

    if project:
        ig = project.integration
        if ig:
            ig.spreadsheet_id = sid
            ig.sheet_acts = s.static_sheet_acts
            ig.sheet_costs = s.static_sheet_costs
            ig.sheet_specialists = s.static_sheet_specialists
            ig.sheet_metrics = s.static_sheet_metrics
        project.name = s.static_project_name
        await db.flush()
        await db.execute(delete(Project).where(Project.user_id == user.id, Project.id != project.id))
        await db.flush()
        return project

    await db.execute(delete(Project).where(Project.user_id == user.id))
    await db.flush()

    project = Project(name=s.static_project_name, user_id=user.id)
    db.add(project)
    await db.flush()
    integ = ProjectIntegration(
        project_id=project.id,
        spreadsheet_id=sid,
        sheet_acts=s.static_sheet_acts,
        sheet_costs=s.static_sheet_costs,
        sheet_specialists=s.static_sheet_specialists,
        sheet_metrics=s.static_sheet_metrics,
    )
    db.add(integ)
    await db.flush()
    res = await db.execute(
        select(Project).where(Project.id == project.id).options(selectinload(Project.integration))
    )
    return res.scalar_one()
