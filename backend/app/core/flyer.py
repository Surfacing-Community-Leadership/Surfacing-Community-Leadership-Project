"""Headline and blurb copy for an event flyer.

Three rules shape everything in this module:

  * **The key stays here.** Gemini is called from the server, never the browser.
    The frontend asks *us* for copy; it never learns the key exists.
  * **The model is never told the address.** It receives the title, description,
    host's display name, when it happens, and the neighbourhood — nothing that
    could put a stranger on someone's doorstep. This matters most for a help
    request, where the address *is* somebody's home.
  * **It cannot fail.** If Gemini is unconfigured, slow, rate-limited or broken,
    `flyer_copy()` returns templated copy built from the event's own fields. The
    failure is logged for us; the user just sees a working flyer. A feature that
    breaks when a free tier runs out isn't free, it's fragile.

The model is also explicitly forbidden from inventing facts. A flyer is a factual
document — an invented "free food!" on a poster is a real-world problem, not a
cosmetic one — so the prompt constrains it to rephrasing what it was given, and
anything it returns is length-capped before it reaches a template.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime

from app.core.config import settings

log = logging.getLogger("ours.flyer")

# How long to wait on Gemini before giving up and using templated copy. A person
# is staring at a spinner, so this is a UX budget rather than a network one.
TIMEOUT_SECONDS = 12

# Ceilings applied to whatever comes back, so a runaway response can't blow the
# flyer's layout apart.
MAX_HEADLINE_CHARS = 70
MAX_BLURB_CHARS = 220
WANTED_OPTIONS = 3


@dataclass(frozen=True)
class CopyOption:
    headline: str
    blurb: str


@dataclass(frozen=True)
class FlyerCopy:
    options: list[CopyOption]
    # True when these came from the templated fallback rather than the model.
    # The API reports it so the UI can be honest about what the user is looking
    # at, and so tests can assert which path ran.
    generated: bool


def _when(starts_at: datetime) -> str:
    """A human date for the prompt and the fallback: 'Saturday 9 August, 3:00 PM'."""
    # %-d / %-I are platform-specific; build it without them so this behaves the
    # same on macOS and in the Linux container.
    day = starts_at.strftime("%A %d %B").replace(" 0", " ")
    hour = starts_at.strftime("%I:%M %p").lstrip("0")
    return f"{day}, {hour}"


KIND_WORDS = {
    "gathering": ("gathering", "Come along"),
    "help_request": ("neighbour asking for a hand", "Lend a hand"),
    "volunteer_work": ("volunteering shift", "Join in"),
}


def fallback_copy(
    *,
    title: str,
    description: str | None,
    host_name: str | None,
    neighborhood: str | None,
    starts_at: datetime,
    kind: str,
) -> FlyerCopy:
    """Templated copy from the event's own words — the substitution fallback.

    Deliberately plain. It is not trying to impersonate the model; it is trying
    to produce a flyer somebody would still be happy to print. Every value here
    came from the host, so none of it can be wrong.
    """
    noun, call = KIND_WORDS.get(kind, KIND_WORDS["gathering"])
    where = neighborhood or "your neighbourhood"
    who = host_name or "A neighbour"
    when = _when(starts_at)

    # First sentence of the host's own description, if they wrote one.
    detail = ""
    if description:
        first = description.strip().split("\n")[0].strip()
        if first:
            detail = first if len(first) <= MAX_BLURB_CHARS else first[: MAX_BLURB_CHARS - 1] + "…"

    options = [
        CopyOption(
            headline=title[:MAX_HEADLINE_CHARS],
            blurb=(detail or f"{who} is hosting a {noun} in {where}. {when}.")[:MAX_BLURB_CHARS],
        ),
        CopyOption(
            headline=f"{call} in {where}"[:MAX_HEADLINE_CHARS],
            blurb=f"{title} — {when}. Hosted by {who}."[:MAX_BLURB_CHARS],
        ),
    ]
    return FlyerCopy(options=options, generated=False)


PROMPT = """You are writing copy for a printed paper flyer for a neighbourhood \
event. It will be stuck on a lamppost or a shop window.

Write exactly {wanted} options. Each option is a short headline and a short \
blurb.

Rules you must follow:
- Use ONLY the facts given below. Do not invent anything — no prices, no food, \
no activities, no attendance numbers, no claims about the host, no street names.
- If a fact is missing, leave it out rather than guessing.
- Headline: at most {max_headline} characters. Punchy, warm, plain language.
- Blurb: at most {max_blurb} characters, one or two sentences. It should make a \
neighbour want to turn up.
- No emoji, no hashtags, no exclamation-mark stacking, no ALL CAPS.
- Do not repeat the date or the neighbourhood name in the blurb — the flyer \
already prints those separately.
- Non-partisan and welcoming. Nothing political.

The event:
- What it is: {kind}
- Title: {title}
- Host: {host}
- When: {when}
- Neighbourhood: {neighborhood}
- Description written by the host: {description}

Return JSON only, shaped exactly like this:
{{"options": [{{"headline": "...", "blurb": "..."}}]}}"""


def _clean(value: object, limit: int) -> str:
    """Coerce whatever the model returned into a safe single-line string."""
    text = str(value or "").replace("\n", " ").strip()
    # Models sometimes wrap a value in quotes despite the JSON contract.
    text = text.strip('"').strip()
    return text[:limit]


def _parse(raw: str) -> list[CopyOption]:
    """Pull options out of the model's reply, tolerating a fenced code block."""
    body = raw.strip()
    if body.startswith("```"):
        body = body.split("```")[1]
        if body.startswith("json"):
            body = body[4:]
    data = json.loads(body)

    options: list[CopyOption] = []
    for item in data.get("options", [])[:WANTED_OPTIONS]:
        headline = _clean(item.get("headline"), MAX_HEADLINE_CHARS)
        blurb = _clean(item.get("blurb"), MAX_BLURB_CHARS)
        # A half-empty option is worse than one fewer option.
        if headline and blurb:
            options.append(CopyOption(headline=headline, blurb=blurb))
    return options


async def flyer_copy(
    *,
    title: str,
    description: str | None,
    host_name: str | None,
    neighborhood: str | None,
    starts_at: datetime,
    kind: str,
) -> FlyerCopy:
    """Copy options for a flyer. Never raises, never returns empty.

    Note what is NOT in this signature: the address. The caller cannot leak one
    to the model even by accident.
    """
    fallback = fallback_copy(
        title=title,
        description=description,
        host_name=host_name,
        neighborhood=neighborhood,
        starts_at=starts_at,
        kind=kind,
    )

    if not settings.gemini_api_key:
        log.info("flyer: GEMINI_API_KEY unset — using templated copy")
        return fallback

    prompt = PROMPT.format(
        wanted=WANTED_OPTIONS,
        max_headline=MAX_HEADLINE_CHARS,
        max_blurb=MAX_BLURB_CHARS,
        kind=KIND_WORDS.get(kind, KIND_WORDS["gathering"])[0],
        title=title,
        host=host_name or "a neighbour",
        when=_when(starts_at),
        neighborhood=neighborhood or "not given",
        description=(description or "none given").strip()[:1500],
    )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.9,
                max_output_tokens=600,
                # A hard server-side deadline, so a hanging call can't hold a
                # request open indefinitely. Milliseconds.
                http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000),
            ),
        )
        options = _parse(response.text or "")
    except Exception as exc:
        # Deliberately broad: an unconfigured key, a quota error, a timeout, a
        # malformed reply and an SDK change all have the same correct response —
        # give the user the templated flyer and record why for us.
        log.warning("flyer: Gemini call failed (%s: %s) — using templated copy",
                    type(exc).__name__, exc)
        return fallback

    if not options:
        log.warning("flyer: Gemini returned no usable options — using templated copy")
        return fallback

    return FlyerCopy(options=options, generated=True)
