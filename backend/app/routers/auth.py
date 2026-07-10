from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users.exceptions import InvalidPasswordException, UserAlreadyExists

from app.core.auth import (
    UserManager,
    cookie_transport,
    get_jwt_strategy,
    get_user_manager,
)
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
    # registration form so the profile is never empty.
    db.add(Profile(user_id=user.id, display_name=payload.display_name, avatar_key="default"))
    await db.commit()
    return user


@router.post("/login", status_code=204)
async def login(
    payload: LoginRequest,
    user_manager: UserManager = Depends(get_user_manager),
):
    credentials = OAuth2PasswordRequestForm(
        username=payload.email, password=payload.password, scope=""
    )
    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid email or password")
    token = await get_jwt_strategy().write_token(user)
    # The token travels only inside an httpOnly cookie — the response body is
    # empty and JavaScript never sees the JWT.
    return await cookie_transport.get_login_response(token)


@router.post("/logout", status_code=204)
async def logout(user: CurrentUser):
    # Clears the auth cookie. (The JWT inside remains technically valid until
    # expiry — a token blocklist is the production-grade upgrade.)
    return await cookie_transport.get_logout_response()
