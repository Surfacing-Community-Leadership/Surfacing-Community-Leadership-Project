from typing import Literal

from pydantic import BaseModel, Field

from app.core.assistant import MAX_MESSAGE_CHARS, MAX_TURNS


class TurnIn(BaseModel):
    """One message in the transcript the browser sends back each time.

    The conversation is held by the browser, not by us — nothing about somebody's
    half-formed idea is stored on the server. That makes the transcript
    untrusted input like any other, which is what the limits below are for: the
    caps are enforced here, not assumed of the client that sent them.
    """

    role: Literal["you", "guide"]
    text: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class TurnRequest(BaseModel):
    # Everything said so far, oldest first, ending with the person's new message.
    transcript: list[TurnIn] = Field(min_length=1, max_length=MAX_TURNS)


class DraftRead(BaseModel):
    """The draft as it stands, which the browser renders and eventually pours
    into the ordinary event form.

    There is no address field and no coordinates here, and there is none in
    `core.assistant.Draft` either. That is the point: the pin is placed by a
    person looking at a map.
    """

    kind: str | None = None
    title: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    capacity: int | None = None
    tag_slug: str | None = None
    # Their own words about when and where, shown beside the real fields as
    # reminders. Never used as values.
    timing_hint: str | None = None
    place_hint: str | None = None


class TurnRead(BaseModel):
    reply: str
    draft: DraftRead
    # The draft is complete enough to hand over to the form.
    ready: bool
    # No more turns left in this conversation; the UI stops offering the input
    # box and offers the form instead.
    exhausted: bool
    remaining_today: int
    daily_limit: int


class AssistantStatus(BaseModel):
    """Asked before the entry point is drawn.

    `available` false means the deployment has no Gemini key, or the person has
    used up today's budget. Either way the UI hides the guide rather than
    offering a button that fails — the ordinary form is always there.
    """

    available: bool
    remaining_today: int
    daily_limit: int
    max_turns: int
