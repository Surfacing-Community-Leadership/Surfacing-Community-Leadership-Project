import secrets
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi_users.password import PasswordHelper
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
from app.core.oauth import (
    GoogleError,
    authorize_url,
    exchange_code_for_profile,
    google_enabled,
    make_state,
    read_state,
)
from app.core.orgs import should_auto_verify
from app.models import OAuthAccount, Profile, User
from app.routers.deps import DB, CurrentUser
from app.schemas.auth import (
    AuthProviders,
    ConfirmEmailPayload,
    ConfirmEmailResult,
    LoginRequest,
    RegisterRequest,
    UserCreate,
    UserRead,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Hashes the throwaway password an OAuth-only account is given.
password_helper = PasswordHelper()


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


@router.get("/providers", response_model=AuthProviders)
async def list_providers():
    """Which third-party sign-ins are configured, so the UI can hide a button
    that would only lead to an error."""
    return AuthProviders(google=google_enabled())


@router.get("/google/start")
async def google_start(next: str = "/map"):
    """Send the browser to Google's consent screen."""
    if not google_enabled():
        raise HTTPException(status_code=503, detail="Google sign-in isn't configured")
    # Only allow same-site destinations, so ?next= can't be used to bounce
    # someone to another origin after signing in.
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/map"
    return RedirectResponse(authorize_url(make_state(safe_next)), status_code=307)


@router.get("/google/callback")
async def google_callback(
    db: DB,
    request: Request,
    strategy: DatabaseStrategy = Depends(get_database_strategy),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Finish the round trip: sign the person in, creating an account if needed.

    Ends in a redirect either way — this URL is opened by the browser, not by
    our own JavaScript, so an error has to be shown as a page rather than a JSON
    body.
    """
    if not google_enabled():
        raise HTTPException(status_code=503, detail="Google sign-in isn't configured")

    if error or not code or not state:
        # The person cancelled, or Google sent us something unusable.
        return _oauth_failure("Google sign-in was cancelled")

    parsed_state = read_state(state)
    if parsed_state is None:
        # Unsigned, tampered with, or older than STATE_MAX_AGE_SECONDS — this is
        # the CSRF guard on the callback.
        return _oauth_failure("That sign-in link expired — please try again")

    try:
        profile = await exchange_code_for_profile(code)
    except GoogleError as exc:
        return _oauth_failure(str(exc))

    user, is_new = await _user_for_google_profile(db, profile)
    if user is None:
        return _oauth_failure(
            "An account already uses that email. Log in with your password instead."
        )
    if not user.is_active:
        return _oauth_failure("That account has been disabled")

    # Same session + CSRF cookie pair the password login issues.
    token = await strategy.write_token(user)
    landing = parsed_state.get("next") or "/map"
    if is_new:
        landing = "/onboarding"
    response = RedirectResponse(landing, status_code=303)
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=settings.access_token_lifetime_seconds,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        secrets.token_hex(16),
        max_age=settings.access_token_lifetime_seconds,
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
    )
    return response


def _oauth_failure(message: str) -> RedirectResponse:
    return RedirectResponse(f"/login?error={quote(message)}", status_code=303)


async def _user_for_google_profile(db, profile: dict) -> tuple[User | None, bool]:
    """Find or create the local account behind a Google identity.

    Returns (user, is_new). A None user means the email belongs to an existing
    password account that we refuse to take over — see below.
    """
    linked = await db.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == "google",
            OAuthAccount.provider_account_id == profile["sub"],
        )
    )
    if linked is not None:
        return await db.get(User, linked.user_id), False

    existing = await db.scalar(select(User).where(User.email == profile["email"]))
    if existing is not None:
        # Adopting an existing account is only safe when Google vouches for the
        # address; otherwise anyone could create an unverified Google identity
        # claiming someone else's email and walk into their account.
        if not profile["email_verified"]:
            return None, False
        db.add(
            OAuthAccount(
                user_id=existing.id,
                provider="google",
                provider_account_id=profile["sub"],
                email=profile["email"],
            )
        )
        if existing.email_confirmed_at is None:
            existing.email_confirmed_at = datetime.now(timezone.utc)
        await db.commit()
        return existing, False

    # Brand new person. Google sign-in always creates a personal account —
    # organizations register through the email form, where they supply the
    # category and website an admin needs.
    user = User(
        email=profile["email"],
        # OAuth accounts have no password anyone knows; store an unusable random
        # one so the column stays non-null and password login can't succeed.
        hashed_password=password_helper.hash(secrets.token_urlsafe(32)),
        # Google verified the address, so this is genuinely confirmed. Note this
        # sets email_confirmed_at and NOT org_verified — the organization badge
        # is never granted by signing in.
        email_confirmed_at=(
            datetime.now(timezone.utc) if profile["email_verified"] else None
        ),
    )
    db.add(user)
    await db.flush()
    db.add(
        Profile(
            user_id=user.id,
            display_name=profile["name"] or profile["email"].split("@")[0],
            avatar_key="🙂",
        )
    )
    db.add(
        OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_account_id=profile["sub"],
            email=profile["email"],
        )
    )
    await db.commit()
    return user, True


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
