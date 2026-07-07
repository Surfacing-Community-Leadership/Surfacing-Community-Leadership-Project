"""FastAPI app instance: middleware, admin, and router mounting."""
from fastapi import FastAPI

from app.admin import init_admin
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
from app.core.rate_limit import init_rate_limiting

app = FastAPI(title="Surfacing Community Leadership API")

init_rate_limiting(app)
init_admin(app)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(profiles.router, prefix="/api/profiles", tags=["profiles"])
app.include_router(communities.router, prefix="/api/communities", tags=["communities"])
app.include_router(interests.router, prefix="/api/interests", tags=["interests"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(participants.router, prefix="/api/events", tags=["participants"])
app.include_router(connections.router, prefix="/api/connections", tags=["connections"])
app.include_router(blocks.router, prefix="/api/blocks", tags=["blocks"])
app.include_router(messages.router, prefix="/api/events", tags=["messages"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
