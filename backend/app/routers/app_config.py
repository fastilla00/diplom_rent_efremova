# Публичные настройки для фронтенда (без секретов)
from fastapi import APIRouter
from app.config import get_settings

router = APIRouter(tags=["config"])


@router.get("/config")
def get_app_config():
    s = get_settings()
    return {
        "static_project_enabled": s.static_project_enabled,
    }
