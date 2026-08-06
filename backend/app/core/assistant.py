"""The guide: a short conversation that turns "I'd like to do something" into a
draft the person can post.

The blank Create Event form is the moment most good intentions die. Somebody
thinks *I should get my neighbours together*, opens a form asking for a title, a
description, a category, a capacity and a pin on a map, and closes the tab. This
module exists to replace that first screen with a few plain questions.

Four rules shape everything here, and each one is enforced by the code rather
than by the prompt alone:

  * **It never writes anything.** This module returns a `Draft` — words on a
    screen. Creating the event is still `POST /api/events`, still triggered by
    the person pressing the button on the normal form. There is exactly one
    write path into `events`, and the model is not on it.

  * **It cannot produce an address.** Look at `Draft`: there is no `address`
    field and no coordinates. Same discipline as `flyer_copy()` having no
    address parameter — the leak is impossible rather than merely avoided. The
    map pin is placed by the person, on the map, afterwards. For a help request
    the address is somebody's home, and a plausible-but-wrong one that a tired
    user accepts without reading puts a stranger on the wrong doorstep.

  * **It cannot invent a category.** `tag_slug` is checked against the slugs
    actually in the database. A model that returns "block-party" when no such
    interest exists yields no category at all, not a broken form.

  * **It is allowed to be unavailable.** Unlike the flyer, there is no templated
    fallback — you cannot fake a conversation. So this raises, the router
    answers 503, and the UI keeps the ordinary form one click away. The guide is
    additive; nothing in the app may depend on it.

On prompt injection: the transcript is user-controlled text, so assume it can say
anything, including instructions to this module. It does not matter much here,
because the worst outcome is a draft with silly words in it that the person then
reads and edits before pressing Create. Nothing the model returns is executed,
stored, or trusted — every field is length-capped and, where it matters,
checked against a list of things that actually exist.
"""

import json
import logging
from dataclasses import dataclass, replace

from app.core.config import settings
from app.core.gemini import GeminiBusy, generate_json

log = logging.getLogger("ours.assistant")

# A UX budget, not a network one — somebody is watching a typing indicator.
TIMEOUT_SECONDS = 15

# How long one of their messages may be. Generous for a sentence or two, small
# enough that nobody pastes a novel into our prompt.
MAX_MESSAGE_CHARS = 600

# Total messages in a conversation, both sides counted. The point of the guide
# is to get somebody to the form, not to keep them chatting; past a dozen
# messages it has stopped helping and started costing.
MAX_TURNS = 14

# Ceilings on what comes back. Deliberately tighter than the database allows
# (title 200, description 5000): a title somebody will read on a map pin wants
# to be short, and these are a starting point the person edits, not final copy.
MAX_REPLY_CHARS = 400
MAX_TITLE_CHARS = 90
MAX_DESCRIPTION_CHARS = 900
MAX_HINT_CHARS = 120

# Sanity bounds on the two numbers the model may suggest.
MIN_DURATION_MINUTES = 15
MAX_DURATION_MINUTES = 8 * 60
MAX_CAPACITY = 500


class AssistantUnavailable(Exception):
    """The model could not be reached, or said something unusable.

    Raised rather than swallowed. There is no honest fallback for a
    conversation, so the caller's job is to say so and point at the form.
    """


class AssistantBusy(AssistantUnavailable):
    """Rate-limited upstream: the same message would go through in a moment.

    A subclass, so any caller that only cares about "it didn't work" keeps
    working, while one that can say something more useful is free to.
    """


@dataclass(frozen=True)
class Turn:
    # "you" (the person) or "guide" (us). Named for how they read in the prompt.
    role: str
    text: str


@dataclass(frozen=True)
class Draft:
    """What we have understood so far. Every field is optional — an early draft
    is mostly empty, and that is fine to show.

    Note what is absent and cannot be added without a deliberate decision: an
    address, a latitude, a longitude, and a start time. The first three are a
    safety boundary. The last is a correctness one — "Saturday" is ambiguous
    across timezones and week boundaries in ways that are not worth guessing at,
    so the person's own words are kept in `timing_hint` and shown next to the
    date picker as a reminder.
    """

    kind: str | None = None
    title: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    capacity: int | None = None
    tag_slug: str | None = None
    # Their own words about when and where, echoed back beside the real fields.
    # Reminders, never values.
    timing_hint: str | None = None
    place_hint: str | None = None

    def is_usable(self) -> bool:
        """Enough to be worth putting in front of somebody as a form."""
        return bool(self.kind and self.title)


@dataclass(frozen=True)
class Guidance:
    reply: str
    draft: Draft
    # The model thinks the draft is complete enough to hand over. Advisory: the
    # person can hand over whenever they like, and the server forces it once the
    # conversation runs long.
    ready: bool


KIND_BRIEFS = {
    "gathering": (
        "gathering — anyone can turn up and spend time together. A stoop coffee, "
        "a book swap, a kickabout in the park."
    ),
    "help_request": (
        "help_request — this person is asking a neighbour for a hand with "
        "something of their own. A lift to an appointment, help shifting a sofa, "
        "someone to walk the dog for a week."
    ),
    "volunteer_work": (
        "volunteer_work — this organisation needs volunteers for a shift. A "
        "clean-up, a food distribution, a shelter rota."
    ),
}


PROMPT = """You are the guide inside Ours, a neighbourhood app for getting people \
together in person.

You are talking to someone who has thought "I should do something on my street" \
and has not started. Your entire job is to ask a few short questions and turn \
their answers into a draft they can post. You are not a chatbot they are here to \
enjoy — you are the thing standing between them and a blank form, and the \
kindest thing you can do is get out of the way quickly.

HOW TO TALK
- One question at a time. Never a list.
- Two sentences maximum, and usually one.
- Plain warm language. No emoji, no exclamation marks, no marketing voice, no \
"amazing", no "I'd love to".
- Assume they are slightly nervous. Small is a success: six neighbours on a \
stoop is a real event. Never encourage them to make it bigger than they said.
- If they have already told you something, do not ask again.
- When you have enough, say so in one sentence and stop asking.

WHAT YOU ARE FILLING IN
- kind: exactly one of these, and nothing else:
{kinds}
- title: short and concrete, the words a neighbour would read on a map. Not a \
slogan.
- description: two or three sentences in their voice, saying what it is and who \
it is for. Use only what they told you.
- duration_minutes: only if they said or clearly implied how long.
- capacity: only if they mentioned a limit. Leave it out otherwise; most things \
do not need one.
- tag_slug: one of these exact slugs, or null if none fit:
{tags}
- timing_hint: their own words about when, copied, like "Saturday afternoon".
- place_hint: their own words about where, copied, like "the little park by the \
school".

NEVER
- Never ask for a street address, a postcode, or a house number, and never write \
one. The app collects the exact spot on a map afterwards. For a help request \
that address is somebody's home.
- Never ask for a date in a particular format, and never convert what they said \
into one. Put their words in timing_hint. The app has a date picker.
- Never invent a fact they did not give you — no prices, no food, no numbers of \
people, no activities they did not mention.
- Never ask more than one question in a message.

NOT WHAT THIS IS FOR
Ours is non-partisan and is for neighbours meeting neighbours. If they are \
trying to advertise a business or sell something, run a political campaign or \
party activity, organise a patrol or a crime watch or anything about a specific \
person being suspicious, or target any person or group — say plainly and without \
lecturing that Ours is not the place for it, suggest a neighbourly alternative \
if there is an obvious one, and leave every draft field null.

OUTPUT
Return JSON only, shaped exactly like this. Omit any field you do not know yet; \
do not guess to fill it.
{{"reply": "what you say next",
  "draft": {{"kind": null, "title": null, "description": null,
            "duration_minutes": null, "capacity": null, "tag_slug": null,
            "timing_hint": null, "place_hint": null}},
  "ready": false}}

Set "ready" to true only once kind, title and description are all filled and you \
have stopped asking questions.

The draft must be rebuilt in full every time from the whole conversation so far, \
not just your last message.

THE CONVERSATION SO FAR
{transcript}

Reply as the guide."""


def _clean(value: object, limit: int) -> str | None:
    """Coerce whatever the model returned into a safe single-line string."""
    if value is None:
        return None
    text = str(value).replace("\n", " ").strip()
    text = text.strip('"').strip()
    return text[:limit] or None


def _paragraphs(value: object, limit: int) -> str | None:
    """Same, but for the description, where line breaks are worth keeping."""
    if value is None:
        return None
    lines = [line.strip() for line in str(value).splitlines()]
    text = "\n".join(line for line in lines if line).strip()
    return text[:limit] or None


def _bounded_int(value: object, low: int, high: int) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def _parse(raw: str, *, allowed_kinds: tuple[str, ...], tag_slugs: set[str]) -> Guidance:
    """Turn the model's reply into a Guidance, discarding anything untrue.

    Every value is either bounded, or checked against something that actually
    exists. A field the model got wrong becomes absent, never wrong.
    """
    body = raw.strip()
    if body.startswith("```"):
        body = body.split("```")[1]
        if body.startswith("json"):
            body = body[4:]
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")

    reply = _clean(data.get("reply"), MAX_REPLY_CHARS)
    if not reply:
        # A draft with nothing said alongside it reads as the app freezing.
        raise ValueError("no reply text")

    raw_draft = data.get("draft") or {}
    if not isinstance(raw_draft, dict):
        raw_draft = {}

    kind = _clean(raw_draft.get("kind"), 40)
    # A person must not be handed a volunteer shift, and an organisation must
    # not be handed a personal help request — the events API would refuse it,
    # and finding that out at the last button press is a bad way to learn.
    if kind not in allowed_kinds:
        kind = None

    tag_slug = _clean(raw_draft.get("tag_slug"), 60)
    if tag_slug not in tag_slugs:
        tag_slug = None

    draft = Draft(
        kind=kind,
        title=_clean(raw_draft.get("title"), MAX_TITLE_CHARS),
        description=_paragraphs(raw_draft.get("description"), MAX_DESCRIPTION_CHARS),
        duration_minutes=_bounded_int(
            raw_draft.get("duration_minutes"), MIN_DURATION_MINUTES, MAX_DURATION_MINUTES
        ),
        capacity=_bounded_int(raw_draft.get("capacity"), 1, MAX_CAPACITY),
        tag_slug=tag_slug,
        timing_hint=_clean(raw_draft.get("timing_hint"), MAX_HINT_CHARS),
        place_hint=_clean(raw_draft.get("place_hint"), MAX_HINT_CHARS),
    )

    # The model's own "ready" is only believed when the draft backs it up.
    ready = bool(data.get("ready")) and draft.is_usable()
    return Guidance(reply=reply, draft=draft, ready=ready)


def _render(transcript: list[Turn]) -> str:
    if not transcript:
        return "(nothing yet — greet them and ask what they have in mind)"
    speaker = {"you": "Them", "guide": "You"}
    return "\n".join(
        f"{speaker.get(turn.role, 'Them')}: {turn.text[:MAX_MESSAGE_CHARS]}"
        for turn in transcript
    )


def configured() -> bool:
    """Whether the guide can run at all. The UI asks before offering it, so an
    unconfigured deployment simply doesn't show the entry point rather than
    showing a button that always fails."""
    return bool(settings.gemini_api_key)


async def next_turn(
    *,
    transcript: list[Turn],
    allowed_kinds: tuple[str, ...],
    tags: list[tuple[str, str]],
) -> Guidance:
    """The guide's next message, and the draft as it now stands.

    `tags` is (slug, name) for the categories that really exist, so the model
    picks from the live list rather than from whatever it remembers.

    Raises AssistantUnavailable if the model can't be reached or returns
    something unusable. There is no fallback on purpose — see the module note.
    """
    if not configured():
        raise AssistantUnavailable("GEMINI_API_KEY is unset")

    prompt = PROMPT.format(
        kinds="\n".join(f"  - {KIND_BRIEFS[k]}" for k in allowed_kinds if k in KIND_BRIEFS),
        tags="\n".join(f"  - {slug} ({name})" for slug, name in tags) or "  (none)",
        transcript=_render(transcript),
    )

    try:
        raw = await generate_json(
            prompt,
            # Lower than the flyer's 0.9. The flyer wants three copy options
            # that differ from each other; this wants one steady question.
            temperature=0.6,
            timeout_seconds=TIMEOUT_SECONDS,
        )
        return _parse(
            raw,
            allowed_kinds=allowed_kinds,
            tag_slugs={slug for slug, _ in tags},
        )
    except GeminiBusy as exc:
        # Common enough on a free tier to be worth telling apart — see the note
        # on GeminiBusy. Same shape as the failure below, different sentence.
        log.info("assistant: rate-limited upstream (%s)", exc)
        raise AssistantBusy(str(exc)) from exc
    except Exception as exc:
        # Broad on purpose, exactly as in flyer.py: a timeout, a malformed
        # reply and an SDK change all mean the same thing to the person in
        # front of us.
        log.warning(
            "assistant: turn failed (%s: %s)", type(exc).__name__, exc
        )
        raise AssistantUnavailable(str(exc)) from exc


def force_handoff(guidance: Guidance) -> Guidance:
    """Mark a conversation as done because it has gone on long enough.

    The guide is a doorway, not a destination. Once the turn limit is reached we
    stop asking and offer what we have, however thin — a half-filled form the
    person can finish is still better than the blank one they were avoiding.
    """
    return replace(
        guidance,
        reply=(
            guidance.reply
            + "  That's plenty to start with — here's the form with what we have."
        )[:MAX_REPLY_CHARS + 60],
        ready=True,
    )
