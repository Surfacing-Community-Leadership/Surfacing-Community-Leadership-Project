import re

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    secret_key: str
    access_token_lifetime_seconds: int = 60 * 60 * 24  # 24h, per team decision

    # False for local http development; MUST be True behind https in production.
    cookie_secure: bool = False

    cors_origins: list[str] = ["http://localhost:5173"]

    # Free key from developer.ticketmaster.com; only the import script needs it.
    ticketmaster_api_key: str | None = None

    # --- outgoing mail (confirmation links) ------------------------------
    # Unset in development: the confirmation link is logged to the console
    # instead of being sent, so nothing external is required to work on this.
    resend_api_key: str | None = None
    email_from: str = "Ours <onboarding@resend.dev>"
    # Where confirmation links point. In production this is the deployed origin
    # (same origin serves the SPA); locally it's the Vite dev server.
    public_base_url: str = "http://localhost:5173"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        # Managed hosts (Render, Heroku, …) hand out `postgres://` URLs, but the
        # app's async engine needs the asyncpg driver. Rewrite the scheme, and
        # drop libpq's `sslmode` query param, which asyncpg doesn't understand
        # (use the provider's *internal* URL to avoid needing TLS at all).
        if v.startswith("postgres://"):
            v = "postgresql+asyncpg://" + v[len("postgres://"):]
        elif v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://"):]
        v = re.sub(r"[?&]sslmode=\w+", "", v)
        return v


settings = Settings()
