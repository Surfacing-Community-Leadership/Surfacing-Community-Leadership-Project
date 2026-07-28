"""The notice board: what may be posted, for how long, and how much.

A notice is *information about the area*; an event is *an invitation to show
up*. That line is the whole design. Anything that wants RSVPs, a capacity or a
guest list is an event and belongs in the events table — which is why notices
carry no participants, no attendance and no trust tallies.

Three structural rules keep the board quiet, chosen over moderation because
there is nobody on staff to moderate:

  * **Everything expires.** A notice carries an explicit `expires_at`, so the
    board sweeps itself and nothing rots at the bottom of it.
  * **Everyone has a small allowance.** MAX_LIVE_NOTICES at a time, because a
    corkboard has finite space and that scarcity is the feature.
  * **The categories are a closed list.** Free text invites a feed; a fixed set
    of shapes stays skimmable.

DELIBERATELY ABSENT: any "crime & safety" category. Neighborhood apps that ship
one reliably become fear-amplifiers — studies of Nextdoor find its users
perceive more crime regardless of whether crime actually rose — and that is the
opposite of getting neighbors comfortable with each other in person. Reporting
and blocking handle genuine safety problems between people; broadcasting
suspicion to the whole neighborhood is not a feature of this product.
"""

from datetime import datetime, timedelta

# What anyone may post. Ordered as they should appear in the UI.
PERSON_CATEGORIES = (
    "giveaway",        # free to a good home — the one category that forces a handoff
    "lost_found",      # lost or found: a cat, a set of keys
    "recommendation",  # asking neighbors for local know-how
    "offer_help",      # a standing offer of a skill or a spare hour
)

# Additional categories reserved for organization accounts. These carry the
# authority of an institution, so they need the account type behind them.
ORG_ONLY_CATEGORIES = (
    "announcement",    # the library's summer reading program starts Monday
    "service_change",  # street closure, changed hours, cancelled pickup
)

NOTICE_CATEGORIES = PERSON_CATEGORIES + ORG_ONLY_CATEGORIES

# How long a notice lives unless the author picks otherwise. Two weeks is long
# enough for a giveaway to find a taker and short enough that a stale board
# never needs a cleanup crew.
DEFAULT_EXPIRY_DAYS = 14
MAX_EXPIRY_DAYS = 30

# Live notices per author. Expired and resolved ones don't count against it,
# so the allowance replenishes on its own.
MAX_LIVE_NOTICES = 3

# A reply is one line to the poster, not a conversation.
MAX_REPLY_CHARS = 280


def categories_for(account_type: str) -> tuple[str, ...]:
    """The categories this kind of account may post in. An organization gets
    everything — a library giving away chairs is still a giveaway — while a
    person is limited to the neighborly set."""
    if account_type == "organization":
        return NOTICE_CATEGORIES
    return PERSON_CATEGORIES


def is_category_allowed(account_type: str, category: str) -> bool:
    return category in categories_for(account_type)


def default_expires_at(now: datetime) -> datetime:
    return now + timedelta(days=DEFAULT_EXPIRY_DAYS)


def latest_expires_at(now: datetime) -> datetime:
    """The furthest out an author may push an expiry, checked on create and on
    every edit so repeated 'extend' presses can't make a notice immortal."""
    return now + timedelta(days=MAX_EXPIRY_DAYS)
