"""Test fixtures.

The environment variables are set BEFORE importing the app, so the app's
Settings pick up the ours_test database instead of ours_dev — real env vars
take precedence over .env values in pydantic-settings.
"""

import getpass
import os

DB_USER = getpass.getuser()
TEST_DB = "ours_test"
os.environ["DATABASE_URL"] = (
    f"postgresql+asyncpg://{DB_USER}@localhost:5432/{TEST_DB}"
)
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["COOKIE_SECURE"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database import AsyncSessionLocal, Base, engine  # noqa: E402
from app.main import app  # noqa: E402

BASE_URL = "http://test"


@pytest.fixture(scope="session", autouse=True)
async def test_database():
    """Drop and recreate ours_test once per test run, with PostGIS enabled
    and the schema built straight from the models (Base.metadata)."""
    admin_engine = create_async_engine(
        f"postgresql+asyncpg://{DB_USER}@localhost:5432/postgres",
        isolation_level="AUTOCOMMIT",
    )
    async with admin_engine.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        await conn.execute(text(f"CREATE DATABASE {TEST_DB}"))
    await admin_engine.dispose()

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def clean_tables(test_database):
    """Each test starts from an empty database (cascades cover child tables)."""
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE users, events, communities, interests CASCADE")
        )


@pytest.fixture
async def client():
    """An anonymous API client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as c:
        yield c


@pytest.fixture
async def make_user():
    """Factory: register + log in a user, returning a client that carries
    their auth cookie and CSRF header. Usage:
        dylan = await make_user("dylan@example.com", "Dylan")
    """
    clients = []

    async def factory(email, name="Someone", password="password-123"):
        c = AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
        clients.append(c)
        r = await c.post(
            "/api/auth/register",
            json={"email": email, "password": password, "display_name": name},
        )
        assert r.status_code == 201, r.text
        r = await c.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 204, r.text
        c.headers["X-CSRF-Token"] = c.cookies.get("ours_csrf")
        return c

    yield factory
    for c in clients:
        await c.aclose()


@pytest.fixture
async def interest_id():
    """Insert one interest directly (there is no API to create them)."""
    from app.models import Interest

    async with AsyncSessionLocal() as session:
        interest = Interest(name="Gardening", slug="gardening")
        session.add(interest)
        await session.commit()
        await session.refresh(interest)
        return str(interest.id)


@pytest.fixture
async def community_id():
    """Insert one community directly (the create API needs live OSM data)."""
    from app.models import Community

    async with AsyncSessionLocal() as session:
        community = Community(name="Sunset Park", slug="sunset-park")
        session.add(community)
        await session.commit()
        await session.refresh(community)
        return str(community.id)


SUNSET_PARK = {"lat": 40.6552, "lng": -74.0069}


def event_payload(**overrides):
    """A valid gathering in Sunset Park; override any field per test."""
    payload = {
        "kind": "gathering",
        "title": "Board games in the park",
        "location": SUNSET_PARK,
        "address": "41st St entrance",
        "starts_at": "2027-08-01T15:00:00Z",
        "visibility": "public",
    }
    payload.update(overrides)
    return payload
