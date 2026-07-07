"""POST /api/auth/register, /api/auth/login, /api/auth/logout — wraps fastapi-users routers."""
from fastapi import APIRouter

router = APIRouter()
