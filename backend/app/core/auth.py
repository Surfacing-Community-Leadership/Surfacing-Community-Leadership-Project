import uuid

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy.db import (
    AccessTokenDatabase,
    DatabaseStrategy,
)
from fastapi_users.exceptions import InvalidPasswordException
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models import AccessToken, User

AUTH_COOKIE_NAME = "ours_auth"
CSRF_COOKIE_NAME = "ours_csrf"


async def get_user_db(session: AsyncSession = Depends(get_db)):
    yield SQLAlchemyUserDatabase(session, User)


async def get_access_token_db(session: AsyncSession = Depends(get_db)):
    yield SQLAlchemyAccessTokenDatabase(session, AccessToken)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    async def validate_password(self, password: str, user) -> None:
        if len(password) < 8:
            raise InvalidPasswordException(
                reason="Password must be at least 8 characters"
            )
        email = getattr(user, "email", None)
        if email and password.lower() == email.lower():
            raise InvalidPasswordException(reason="Password must not equal your email")


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
):
    yield UserManager(user_db)


# httpOnly cookie: JavaScript can never read the token, which closes the
# XSS-steals-your-session hole. samesite="lax" plus the CSRF middleware in
# main.py handle cross-site request forgery.
cookie_transport = CookieTransport(
    cookie_name=AUTH_COOKIE_NAME,
    cookie_max_age=settings.access_token_lifetime_seconds,
    cookie_secure=settings.cookie_secure,
    cookie_httponly=True,
    cookie_samesite="lax",
)


def get_database_strategy(
    access_token_db: AccessTokenDatabase[AccessToken] = Depends(get_access_token_db),
) -> DatabaseStrategy:
    # Opaque tokens stored server-side: logout deletes the row, so a session
    # can be truly revoked (unlike a stateless JWT).
    return DatabaseStrategy(
        access_token_db, lifetime_seconds=settings.access_token_lifetime_seconds
    )


auth_backend = AuthenticationBackend(
    name="db-cookie",
    transport=cookie_transport,
    get_strategy=get_database_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
