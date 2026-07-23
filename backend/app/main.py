import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.admin import mount_admin
from app.core.auth import AUTH_COOKIE_NAME, CSRF_COOKIE_NAME
from app.core.config import settings
from app.core.database import get_db
from app.routers import (
    auth,
    blocks,
    communities,
    connections,
    events,
    geocode,
    interests,
    messages,
    notifications,
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


# CSRF double-submit check. Cookies are attached by the browser automatically
# (that's the attack), but only same-origin JavaScript can read our csrf
# cookie to echo it in this header — so a match proves the request came from
# our own frontend. Scoped to /api so SQLAdmin's own forms aren't caught.
@app.middleware("http")
async def csrf_protect(request: Request, call_next):
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and request.url.path.startswith("/api")
        and AUTH_COOKIE_NAME in request.cookies
    ):
        cookie = request.cookies.get(CSRF_COOKIE_NAME)
        header = request.headers.get("x-csrf-token")
        if not cookie or cookie != header:
            return JSONResponse(
                status_code=403,
                content={"message": "CSRF check failed — refresh and try again"},
            )
    return await call_next(request)


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
app.include_router(geocode.router)
app.include_router(participants.router)
app.include_router(connections.router)
app.include_router(blocks.router)
app.include_router(messages.router)
app.include_router(notifications.router)
app.include_router(reports.router)

# Uploaded files (avatars) served from local disk in development.
os.makedirs("media/avatars", exist_ok=True)
app.mount("/media", StaticFiles(directory="media"), name="media")

mount_admin(app)


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


# ---- Serve the built frontend (single-origin production deploy) -----------
# In production the React build is served from the same origin as the API, so
# the httpOnly auth cookie + CSRF flow needs no cross-site configuration.
# Skipped in local dev, where Vite serves the SPA and proxies /api here.
# Registered last so every API route, /media and /admin match first.
FRONTEND_DIST = Path(
    os.getenv("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist")
)
if (FRONTEND_DIST / "index.html").is_file():
    app.mount(
        "/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets"
    )

    # Prefixes owned by the backend — never hand these to the SPA fallback.
    _RESERVED = ("api", "media", "admin", "health", "docs", "redoc", "openapi.json")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith(_RESERVED):
            raise HTTPException(status_code=404, detail="Not found")
        # A real static file (favicon, etc.) → serve it; anything else is a
        # client-side route, so return index.html and let React Router handle it.
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
