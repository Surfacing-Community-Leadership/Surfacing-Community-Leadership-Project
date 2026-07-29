"""The notice board: what may be posted, for how long, and how much.

A notice is *information about the area*; an event is *an invitation to show
up*. That line is the whole design. Anything that wants RSVPs, a capacity or a
guest list is an event and belongs in the events table — which is why notices
carry no participants, no attendance and no trust tallies.

Structural rules keep the board quiet, chosen over moderation because there is
nobody on staff to moderate:

  * **Everything expires.** A notice carries an explicit `expires_at` — two
    weeks unless the author picks otherwise, three months at the very most — so
    the board sweeps itself and nothing rots at the bottom of it.
  * **Everyone has an allowance.** A limited number of live notices at a time,
    because a corkboard has finite space and that scarcity is the feature.
    Organizations get a larger one: a library genuinely does have more to
    announce than a neighbour does.
  * **The post types are a closed list.** Free text invites a feed; a fixed set
    of shapes stays skimmable.
  * **No public comment threads.** A reply is one private line to the author,
    and only if they left inquiries open.

DELIBERATELY ABSENT: any "crime & safety" type. Neighborhood apps that ship one
reliably become fear-amplifiers — studies of Nextdoor find its users perceive
more crime regardless of whether crime actually rose — and that is the opposite
of getting neighbors comfortable with each other in person. Reporting and
blocking handle genuine safety problems between people; broadcasting suspicion
to the whole neighborhood is not a feature of this product.
"""

from datetime import datetime, timedelta

# What anyone may post. Ordered as they should appear in the UI: the two
# "somebody needs / is offering something" types first, since those are the ones
# that end in a doorstep handover, then the read-and-know ones.
PERSON_CATEGORIES = (
    "giveaway",        # free to a good home — the type that forces a handoff
    "lost_found",      # lost or found: a cat, a set of keys
    "recommendation",  # asking neighbors for local know-how
    "offer_help",      # a standing offer of a skill or a spare hour
    "news",            # something that happened around here
    "shoutout",        # thanks or credit where it's due
    "blog",            # a longer piece: a story, a reflection, a write-up
)

# Additional types reserved for organization accounts. These carry the authority
# of an institution, so they need the account type behind them.
ORG_ONLY_CATEGORIES = (
    "announcement",    # the library's summer reading program starts Monday
    "service_change",  # street closure, changed hours, cancelled pickup
)

NOTICE_CATEGORIES = PERSON_CATEGORIES + ORG_ONLY_CATEGORIES

# Types that tend to be long. Only used to pick the compose hint and how much
# of the body a card previews — the length limit itself is uniform, because a
# thorough giveaway description shouldn't be punished for being thorough.
LONG_FORM_CATEGORIES = ("blog", "news")

# How long a notice lives unless the author picks otherwise, and the hard
# ceiling. Two weeks suits a lost cat; three months suits a seasonal programme.
DEFAULT_EXPIRY_DAYS = 14
MAX_EXPIRY_DAYS = 90

# The windows offered in the compose form, in days. The form sends an explicit
# expires_at, so this list is presentation only — the server clamps to
# MAX_EXPIRY_DAYS regardless of what arrives.
EXPIRY_CHOICES_DAYS = (7, 14, 30, 90)

# Live notices per author. Expired and resolved ones don't count, so the
# allowance replenishes on its own. Organizations get more room because their
# posting is the point of a verified account, not an indulgence.
MAX_LIVE_NOTICES = 5
MAX_LIVE_NOTICES_ORG = 15

# A reply is one line to the poster, not a conversation.
MAX_REPLY_CHARS = 280

# Body length. Generous enough for a write-up, short of an essay.
MAX_BODY_CHARS = 8000
MIN_BODY_CHARS = 10

# "Post of the day" ranks by stars earned in this trailing window, so a good
# post from this morning can still win against last month's most-starred one.
STAR_WINDOW_HOURS = 24


def categories_for(account_type: str) -> tuple[str, ...]:
    """The post types this kind of account may use. An organization gets
    everything — a library giving away chairs is still a giveaway — while a
    person is limited to the neighborly set."""
    if account_type == "organization":
        return NOTICE_CATEGORIES
    return PERSON_CATEGORIES


def is_category_allowed(account_type: str, category: str) -> bool:
    return category in categories_for(account_type)


def max_live_for(account_type: str) -> int:
    return MAX_LIVE_NOTICES_ORG if account_type == "organization" else MAX_LIVE_NOTICES


def default_expires_at(now: datetime) -> datetime:
    return now + timedelta(days=DEFAULT_EXPIRY_DAYS)


def latest_expires_at(now: datetime) -> datetime:
    """The furthest out an author may push an expiry, checked on create and on
    every edit so repeated 'extend' presses can't make a notice immortal."""
    return now + timedelta(days=MAX_EXPIRY_DAYS)


def star_window_start(now: datetime) -> datetime:
    return now - timedelta(hours=STAR_WINDOW_HOURS)
