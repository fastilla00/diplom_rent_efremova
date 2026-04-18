# Публичные настройки для фронтенда (без секретов)
from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(tags=["config"])


@router.get("/config")
def get_app_config() -> dict[str, bool]:
    """Публичные флаги UI (без секретов), например режим статического проекта."""
    s = get_settings()
    return {
        "static_project_enabled": s.static_project_enabled,
    }
