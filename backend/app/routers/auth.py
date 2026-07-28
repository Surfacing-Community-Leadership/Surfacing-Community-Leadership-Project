import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
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
from app.core.email import (
    make_confirm_token,
    read_confirm_token,
    send_confirmation_email,
)
from app.core.orgs import should_auto_verify
from app.models import Profile, User
from app.routers.deps import DB, CurrentUser
from app.schemas.auth import (
    ConfirmEmailPayload,
    ConfirmEmailResult,
    LoginRequest,
    RegisterRequest,
    UserCreate,
    UserRead,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
async def register(
    payload: RegisterRequest,
    db: DB,
    background_tasks: BackgroundTasks,
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
    is_org = payload.account_type == "organization"
    db.add(
        Profile(
            user_id=user.id,
            display_name=payload.display_name,
            avatar_key="🏛️" if is_org else "🙂",
            account_type=payload.account_type,
            org_category=payload.org_category,
            org_website=payload.org_website,
            org_phone=payload.org_phone,
            org_address=payload.org_address,
            org_contact_name=payload.org_contact_name,
            org_contact_role=payload.org_contact_role,
        )
    )

    await db.commit()

    # The ✓ badge is NOT granted here. An institutional domain only counts once
    # the applicant has proven they can read that inbox, so auto-verification is
    # evaluated when the emailed link is clicked (see confirm_email below).
    background_tasks.add_task(
        send_confirmation_email,
        user.email,
        payload.display_name,
        make_confirm_token(user.id),
    )
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


@router.post("/confirm-email", response_model=ConfirmEmailResult)
async def confirm_email(payload: ConfirmEmailPayload, db: DB):
    """Prove an address is reachable, then re-evaluate the organization badge.

    This is where auto-verification actually happens: an institutional domain
    means something only once someone has demonstrated they read that inbox.
    Deliberately unauthenticated — the signed token is the credential, so the
    link works from whatever device opened the mail.
    """
    user_id = read_confirm_token(payload.token)
    if user_id is None:
        raise HTTPException(
            status_code=400,
            detail="That link is invalid or has expired — ask for a new one",
        )

    user = await db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=400, detail="That link is no longer valid")

    already = user.email_confirmed_at is not None
    if not already:
        user.email_confirmed_at = datetime.now(timezone.utc)

    # Grant the org badge now, if the confirmed address earns it.
    granted = False
    if not user.org_verified:
        account_type = await db.scalar(
            select(Profile.account_type).where(Profile.user_id == user.id)
        )
        if should_auto_verify(account_type or "person", user.email):
            user.org_verified = True
            granted = True

    await db.commit()
    return ConfirmEmailResult(
        email=user.email, already_confirmed=already, organization_verified=granted
    )


@router.post("/confirm-email/request", status_code=202)
async def resend_confirmation(
    db: DB, user: CurrentUser, background_tasks: BackgroundTasks
) -> None:
    """Send a fresh link to the signed-in user's own address. Scoped to the
    current session so it can't be used to probe which emails are registered."""
    if user.email_confirmed_at is not None:
        raise HTTPException(status_code=409, detail="This address is already confirmed")
    display_name = await db.scalar(
        select(Profile.display_name).where(Profile.user_id == user.id)
    )
    background_tasks.add_task(
        send_confirmation_email,
        user.email,
        display_name or "neighbor",
        make_confirm_token(user.id),
    )
