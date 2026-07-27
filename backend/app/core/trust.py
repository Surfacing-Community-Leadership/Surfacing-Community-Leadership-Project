"""A neighbor's public track record.

Three counts, each backed by something that can't be self-declared:

* hosted   — events they ran that have actually started, minus cancellations.
* attended — events they self-confirmed showing up to, which requires writing a
             reflection (see MIN_REFLECTION_WORDS) so bulk-farming costs real
             effort.
* helped   — times the person who asked for help confirmed this neighbor turned
             up. Written by the recipient, never the helper.

Deliberately NOT counted or exposed: help *received*. It says nothing about
whether someone is trustworthy, and publishing it would discourage the very
requests the app exists to enable.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, EventParticipant, HelpThanks, User

# How much writing it takes to self-confirm one event. The friction scales with
# any farming attempt: 30 fake events is 600 words of invention.
MIN_REFLECTION_WORDS = 20

# The ladder, highest rung first — the first rung whose thresholds are all met
# wins. Tune these here; nothing else reads the numbers.
#
# Hosting outranks helping because running something is the leadership step this
# app exists to surface. Adjust if your community's balance differs.
TIERS: tuple[tuple[str, dict[str, int]], ...] = (
    ("Organizer", {"hosted": 5}),
    ("Host", {"hosted": 1}),
    ("Helper", {"helped": 3}),
    ("Regular", {"attended": 3}),
    ("Neighbor", {}),
)


def tier_for(counts: dict[str, int]) -> str:
    """The highest rung whose every threshold is satisfied."""
    for name, thresholds in TIERS:
        if all(counts.get(key, 0) >= need for key, need in thresholds.items()):
            return name
    return TIERS[-1][0]


def word_count(text: str) -> int:
    return len(text.split())


async def trust_record(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Counts + tier + verified flag for one user. Four cheap aggregates."""
    hosted = await db.scalar(
        select(func.count())
        .select_from(Event)
        .where(
            Event.host_id == user_id,
            Event.status != "cancelled",
            # Only events that have actually begun — scheduling something for
            # next year shouldn't earn a rung today.
            Event.starts_at <= func.now(),
        )
    )
    attended = await db.scalar(
        select(func.count())
        .select_from(EventParticipant)
        .where(
            EventParticipant.user_id == user_id,
            EventParticipant.status == "attended",
        )
    )
    helped = await db.scalar(
        select(func.count())
        .select_from(HelpThanks)
        .where(HelpThanks.helper_id == user_id)
    )
    verified = await db.scalar(select(User.is_verified).where(User.id == user_id))

    counts = {
        "hosted": hosted or 0,
        "attended": attended or 0,
        "helped": helped or 0,
    }
    return {**counts, "verified": bool(verified), "tier": tier_for(counts)}
