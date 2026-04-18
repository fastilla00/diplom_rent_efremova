# EcomProfit Guard — dependencies
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User

# Тип-алиас async-сессии БД для внедрения через Depends(get_db)
SessionDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user_id(session: SessionDep) -> int | None:
    """Заготовка: идентификатор пользователя из сессии (сейчас не используется)."""
    # TODO: resolve from JWT or session cookie
    return None


CurrentUserId = Annotated[int | None, Depends(get_current_user_id)]
