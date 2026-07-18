import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users.exceptions import InvalidPasswordException, UserAlreadyExists

from app.core.auth import (
    AUTH_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    UserManager,
    cookie_transport,
    get_database_strategy,
    get_user_manager,
)
from app.core.config import settings
from app.models import Profile
from app.routers.deps import DB, CurrentUser
from app.schemas.auth import LoginRequest, RegisterRequest, UserCreate, UserRead

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
async def register(
    payload: RegisterRequest,
    db: DB,
    user_manager: UserManager = Depends(get_user_manager),
):
    try:
        user = await user_manager.create(
            UserCreate(email=payload.email, password=payload.password), safe=True
        )
    except UserAlreadyExists:
        raise HTTPException(status_code=400, detail="Email is already registered")
    except InvalidPasswordException as exc:
        raise HTTPException(status_code=422, detail=exc.reason)

    # Every user gets a profile at birth; display_name comes from the
    # registration form so the profile is never empty. avatar_key doubles as an
    # emoji label when it isn't an uploaded file path, so a neutral emoji is a
    # sensible placeholder until they upload a photo (NOT the literal "default",
    # which would render as that word).
    db.add(Profile(user_id=user.id, display_name=payload.display_name, avatar_key="🙂"))
    await db.commit()
    return user


@router.post("/login", status_code=204)
async def login(
    payload: LoginRequest,
    user_manager: UserManager = Depends(get_user_manager),
    strategy: DatabaseStrategy = Depends(get_database_strategy),
):
    credentials = OAuth2PasswordRequestForm(
        username=payload.email, password=payload.password, scope=""
    )
    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    token = await strategy.write_token(user)  # creates the session row
    response = await cookie_transport.get_login_response(token)
    # Second, JS-readable cookie for CSRF double-submit: the frontend echoes
    # its value in an X-CSRF-Token header, which a hostile site cannot forge
    # because it can't read our cookies.
    response.set_cookie(
        CSRF_COOKIE_NAME,
        secrets.token_hex(16),
        max_age=settings.access_token_lifetime_seconds,
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
    )
    return response


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    user: CurrentUser,
    strategy: DatabaseStrategy = Depends(get_database_strategy),
):
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        # Delete the session row — the token is dead server-side, not just
        # forgotten by the browser.
        await strategy.destroy_token(token, user)
    response = await cookie_transport.get_logout_response()
    response.delete_cookie(CSRF_COOKIE_NAME)
    return response
