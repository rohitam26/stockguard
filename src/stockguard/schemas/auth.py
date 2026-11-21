from pydantic import BaseModel, ConfigDict, Field
from stockguard.models.user import UserRole


class UserRegisterRequest(BaseModel):
    email: str = Field(
        min_length=3, max_length=255, pattern=r"^[\w\.\+\-]+@[a-zA-Z0-9\.\-]+\.[a-zA-Z]{2,}$"
    )
    password: str = Field(min_length=8, description="Minimum 8 characters")
    full_name: str | None = None
    role: UserRole = UserRole.CUSTOMER


class UserLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user_id: str
    email: str
    role: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RevokeTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None = None
    role: str
    is_active: bool
