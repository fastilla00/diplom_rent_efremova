# EcomProfit Guard — auth schemas
from pydantic import BaseModel


class UserInfo(BaseModel):
    id: int
    email: str | None
    name: str | None
    picture: str | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class AuthCallbackBody(BaseModel):
    code: str
    state: str | None = None
