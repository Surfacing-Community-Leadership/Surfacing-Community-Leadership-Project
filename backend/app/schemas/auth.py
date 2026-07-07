from pydantic import BaseModel, EmailStr
from uuid import UUID


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str


class RegisterResponse(BaseModel):
    id: UUID
    email: EmailStr
    is_verified: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str


class UserMeResponse(BaseModel):
    id: UUID
    email: EmailStr
    is_verified: bool
    is_superuser: bool
