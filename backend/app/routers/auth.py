# EcomProfit Guard — auth router
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.auth import TokenResponse, UserInfo
from app.services.google_auth import auth_url, credentials_from_code
from app.core.security import create_token, decode_token
from app.schemas.auth import AuthCallbackBody

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/google")
def google_login() -> dict[str, str]:
    """Возвращает URL входа через Google OAuth и одноразовый `state` для защиты от CSRF."""
    state = secrets.token_urlsafe(16)
    url = auth_url(state)
    return {"url": url, "state": state}


@router.post("/callback")
async def auth_callback(body: AuthCallbackBody, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Обменивает код OAuth на токены Google, создаёт/обновляет пользователя и выдаёт JWT приложения."""
    code = (body.code or "").strip()
    state = (body.state or "").strip()
    if not code:
        raise HTTPException(400, detail="Missing code")
    if not state:
        raise HTTPException(400, detail="Missing state; try logging in again")
    try:
        creds, email, name, google_id = credentials_from_code(code, state)
    except Exception as e:
        msg = str(e).strip() or "Unknown OAuth error"
        raise HTTPException(400, detail=f"OAuth error: {msg}")
    if not creds or not creds.token:
        raise HTTPException(400, "Failed to get credentials")
    if not google_id:
        google_id = email or str(id(creds))
    res = await db.execute(select(User).where(User.google_id == google_id))
    user = res.scalar_one_or_none()
    if user:
        user.email = email or user.email
        user.name = name or user.name
        user.access_token = creds.token
        user.refresh_token = getattr(creds, "refresh_token", None) or user.refresh_token
        if creds.expiry:
            user.token_expires_at = creds.expiry
        await db.flush()
    else:
        user = User(
            google_id=google_id,
            email=email,
            name=name,
            access_token=creds.token,
            refresh_token=getattr(creds, "refresh_token"),
            token_expires_at=creds.expiry if creds.expiry else None,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
    token = create_token(user.id)
    return TokenResponse(
        access_token=token,
        user=UserInfo(id=user.id, email=user.email, name=user.name, picture=user.picture),
    )


async def get_current_user_id(request: Request) -> int | None:
    """Извлекает id пользователя из заголовка `Authorization: Bearer <JWT>`."""
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return decode_token(auth[7:].strip())
    return None


async def require_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """Зависимость: текущий пользователь по JWT или HTTP 401."""
    uid = await get_current_user_id(request)
    if not uid:
        raise HTTPException(401, "Not authenticated")
    res = await db.execute(select(User).where(User.id == uid))
    user = res.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "User not found")
    return user


@router.get("/me", response_model=UserInfo)
async def current_user(user: User = Depends(require_user)) -> UserInfo:
    """Профиль текущего пользователя по JWT."""
    return UserInfo(id=user.id, email=user.email, name=user.name, picture=user.picture)
