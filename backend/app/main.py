from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import get_db
from app.routers import (
    auth,
    blocks,
    communities,
    connections,
    events,
    interests,
    messages,
    participants,
    profiles,
    reports,
    users,
)

app = FastAPI(title="Ours API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# The API contract promises {"message": ...} error bodies; FastAPI's
# defaults use {"detail": ...}, so we reshape them here in one place.
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": str(exc.detail)},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"message": "Validation error", "errors": jsonable_encoder(exc.errors())},
    )


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profiles.router)
app.include_router(communities.router)
app.include_router(interests.router)
app.include_router(events.router)
app.include_router(participants.router)
app.include_router(connections.router)
app.include_router(blocks.router)
app.include_router(messages.router)
app.include_router(reports.router)


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}
