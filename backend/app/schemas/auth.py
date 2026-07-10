import uuid

from fastapi_users import schemas as fu_schemas
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(fu_schemas.BaseUserCreate):
    """Internal shape handed to fastapi-users' UserManager."""


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str = Field(min_length=1, max_length=80)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    is_verified: bool


class UserMe(UserRead):
    is_superuser: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
