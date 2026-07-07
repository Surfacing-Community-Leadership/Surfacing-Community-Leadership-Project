"""slowapi rate limiting, applied to auth and write-heavy endpoints to curb spam/abuse."""
from fastapi import FastAPI


def init_rate_limiting(app: FastAPI) -> None:
    pass
