from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    secret_key: str
    access_token_lifetime_seconds: int = 60 * 60 * 24  # 24h, per team decision

    # False for local http development; MUST be True behind https in production.
    cookie_secure: bool = False

    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
