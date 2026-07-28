"""Google sign-in, implemented directly against Google's endpoints.

Deliberately not using fastapi-users' OAuth router. Its `oauth_callback` takes
`is_verified_by_default`, which writes the flag this project uses for the
*organization* badge — and because Google really does verify addresses, the
natural wiring would hand a badge to every Gmail signup. Here the mapping is
explicit and narrow:

    Google says email_verified  →  users.email_confirmed_at
    organization badge          →  untouched (earned only via core/orgs.py)

The token exchange happens server-side over TLS and the profile is read from
Google's userinfo endpoint, so there's no ID-token signature to verify locally.
Uses httpx and itsdangerous — both already dependencies.
"""

import logging
import secrets
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings

logger = logging.getLogger("ours.oauth")

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"

# Just identity — no Gmail, Drive or contacts access is requested.
SCOPES = "openid email profile"

_STATE_SALT = "google-oauth-state"
STATE_MAX_AGE_SECONDS = 600  # 10 minutes to complete the round trip


def google_enabled() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def redirect_uri() -> str:
    """Must match a redirect URI registered in the Google Cloud console."""
    base = settings.public_base_url.strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    return f"{base}/api/auth/google/callback"


def _state_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt=_STATE_SALT)


def make_state(next_path: str = "/map") -> str:
    """A signed, expiring state parameter. Carries a nonce so the callback can
    prove the round trip started here (CSRF), plus where to land afterwards."""
    return _state_serializer().dumps(
        {"nonce": secrets.token_urlsafe(16), "next": next_path}
    )


def read_state(state: str) -> dict | None:
    try:
        value = _state_serializer().loads(state, max_age=STATE_MAX_AGE_SECONDS)
    except (SignatureExpired, BadSignature):
        return None
    return value if isinstance(value, dict) else None


def authorize_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        # Always show the chooser so a shared browser doesn't silently reuse an
        # account, and don't ask for offline access we have no use for.
        "prompt": "select_account",
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


class GoogleError(Exception):
    """Google refused the exchange, or returned something unusable."""


async def exchange_code_for_profile(code: str) -> dict:
    """Swap the one-time code for the signed-in person's Google profile.

    Returns {sub, email, email_verified, name}. Raises GoogleError on any
    failure — the caller turns that into a redirect with an error message rather
    than leaking Google's response.
    """
    async with httpx.AsyncClient(timeout=10) as http:
        try:
            token_response = await http.post(
                TOKEN_ENDPOINT,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": redirect_uri(),
                    "grant_type": "authorization_code",
                },
            )
        except httpx.HTTPError as exc:
            raise GoogleError("Could not reach Google") from exc

        if token_response.status_code >= 400:
            logger.warning("Google token exchange failed: %s", token_response.text)
            raise GoogleError("Google rejected the sign-in")

        access_token = token_response.json().get("access_token")
        if not access_token:
            raise GoogleError("Google returned no access token")

        try:
            profile_response = await http.get(
                USERINFO_ENDPOINT,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.HTTPError as exc:
            raise GoogleError("Could not reach Google") from exc

    if profile_response.status_code >= 400:
        raise GoogleError("Could not read your Google profile")

    profile = profile_response.json()
    if not profile.get("sub") or not profile.get("email"):
        raise GoogleError("Google did not share an email address")
    return {
        "sub": str(profile["sub"]),
        "email": str(profile["email"]).lower(),
        # Google sends this as a real bool, but be liberal about the string form.
        "email_verified": profile.get("email_verified") in (True, "true", "True"),
        "name": (profile.get("name") or "").strip(),
    }
