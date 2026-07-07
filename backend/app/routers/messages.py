"""GET/POST /api/events/{id}/messages — event-scoped only, no open user-to-user chat."""
from fastapi import APIRouter

router = APIRouter()
