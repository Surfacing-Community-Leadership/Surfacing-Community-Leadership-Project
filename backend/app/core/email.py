"""Confirmation emails: signing the link, and getting it delivered.

Tokens are stateless — an itsdangerous signature over the user id, salted for
this one purpose and checked against an expiry. No table to clean up, and
rotating SECRET_KEY invalidates every outstanding link.

Delivery has two backends and picks itself:
  * RESEND_API_KEY set  → posts to Resend (uses httpx, already a dependency).
  * otherwise           → logs the link to the server console, so local
                          development and tests work with no mail account.
"""

import logging
from urllib.parse import quote

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings

logger = logging.getLogger("ours.email")

# Namespaced so a token minted here can never be replayed against some other
# signed-token feature added later.
_SALT = "email-confirm"
CONFIRM_MAX_AGE_SECONDS = 60 * 60 * 48  # 48 hours


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt=_SALT)


def make_confirm_token(user_id) -> str:
    return _serializer().dumps(str(user_id))


def read_confirm_token(token: str) -> str | None:
    """The user id the token was minted for, or None if it's expired, tampered
    with, or signed by a different key."""
    try:
        return _serializer().loads(token, max_age=CONFIRM_MAX_AGE_SECONDS)
    except (SignatureExpired, BadSignature):
        return None


def confirm_link(token: str) -> str:
    # Hosts sometimes expose only a bare hostname (Render's `property: host`),
    # and a link without a scheme isn't clickable in a mail client — so assume
    # https when none is given.
    base = settings.public_base_url.strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    return f"{base}/confirm-email?token={quote(token)}"


def _body(display_name: str, link: str) -> tuple[str, str]:
    subject = "Confirm your email for Ours"
    html = f"""\
<div style="font-family:system-ui,sans-serif;font-size:15px;line-height:1.6;color:#201e1d">
  <p>Hi {display_name},</p>
  <p>Confirm this address so we know we can reach you:</p>
  <p><a href="{link}"
        style="display:inline-block;background:#c67139;color:#f5ead8;
               padding:12px 22px;border-radius:999px;text-decoration:none;
               font-weight:600">Confirm my email</a></p>
  <p style="color:#6f6552;font-size:13px">
    Or paste this into your browser:<br>{link}
  </p>
  <p style="color:#6f6552;font-size:13px">
    The link works for 48 hours. If you didn't sign up for Ours, you can ignore
    this — nothing will happen.
  </p>
</div>"""
    return subject, html


async def send_confirmation_email(to: str, display_name: str, token: str) -> None:
    """Best-effort delivery. Never raises: a mail outage must not fail the
    signup that triggered it — the user can always ask for a fresh link."""
    link = confirm_link(token)
    subject, html = _body(display_name, link)

    if not settings.resend_api_key:
        # No provider configured (local dev, CI): make the link findable.
        logger.warning("Email not configured — confirm link for %s: %s", to, link)
        return

    try:
        async with httpx.AsyncClient(timeout=10) as http:
            response = await http.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.email_from,
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
            )
        if response.status_code >= 400:
            logger.error("Resend rejected the mail to %s: %s", to, response.text)
    except httpx.HTTPError as exc:
        logger.error("Could not send confirmation mail to %s: %s", to, exc)
