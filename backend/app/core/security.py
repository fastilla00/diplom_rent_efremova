# EcomProfit Guard — JWT
import jwt
from datetime import datetime, timedelta
from app.config import get_settings

ALGORITHM = "HS256"


def create_token(user_id: int) -> str:
    settings = get_settings()
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(days=7)},
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> int | None:
    try:
        settings = get_settings()
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return int(payload.get("sub", 0)) or None
    except Exception:
        return None
