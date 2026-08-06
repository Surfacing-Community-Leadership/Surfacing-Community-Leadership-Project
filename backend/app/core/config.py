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

    # --- Google sign-in ---------------------------------------------------
    # From a Google Cloud OAuth 2.0 client. Unset disables the feature: the
    # button is hidden and the endpoints report it as unavailable.
    google_client_id: str | None = None
    google_client_secret: str | None = None

    # --- flyer copy (Gemini) ----------------------------------------------
    # Server-side only. The key must never reach the browser: the frontend
    # calls our endpoint, our endpoint calls Gemini. Unset is a supported
    # state — the flyer still works, on templated copy built from the event's
    # own fields, so nothing breaks when the key is missing or the free tier
    # is exhausted.
    gemini_api_key: str | None = None
    # An alias, not a pinned version, and that is the point: `gemini-2.0-flash`
    # was the default here until Google set its free-tier quota to a hard zero,
    # at which point every flyer in production silently fell back to templated
    # copy — working, but not what anyone meant. An alias follows whatever the
    # free tier currently serves. Override in the environment to pin a version.
    gemini_model: str = "gemini-flash-latest"
    # Generations per person per day. A guard on the free tier, not a
    # monetisation lever — one enthusiastic host shouldn't be able to spend
    # everyone else's quota.
    flyer_daily_limit: int = 10

    # --- the guide (Gemini, same key) -------------------------------------
    # The chat that walks someone through starting an event. Shares the key
    # above but NOT the counter: a flyer is one call, a conversation is five
    # or ten, so a shared budget would mean talking one event through ate a
    # week of flyers. Unset key disables the guide entirely — the entry point
    # is hidden and the ordinary form is untouched.
    assistant_daily_limit: int = 40

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
