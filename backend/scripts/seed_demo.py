"""Seed the development database with realistic demo data for user testing.

This is NOT a migration. Migrations carry schema and reference data every
environment needs (e.g. the interests taxonomy). This is throwaway,
re-runnable demo data for one dev machine, so it lives in scripts/ and is
run by hand:

    cd backend
    .venv/bin/python scripts/seed_demo.py

Each run WIPES users/events/communities (cascading to profiles, RSVPs,
connections, messages, blocks, reports, sessions) and rebuilds a clean,
known state. Interests survive (separate table, owned by a migration).

Safety: refuses to run unless DATABASE_URL points at a *_dev database,
so it can never be aimed at production data. Override with --force.

All demo accounts share the password below and can log in immediately.
Everything clusters around CENTER — the same spot the app's map falls back
to when geolocation is denied, so denying the browser location prompt drops
you straight into the populated neighborhood.
"""

import asyncio
import math
import random
import sys
from datetime import datetime, timedelta, timezone

from fastapi_users.password import PasswordHelper
from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.geo import wkt_point
from app.models import (
    Community,
    Connection,
    Event,
    EventParticipant,
    Interest,
    Notification,
    OrgFollow,
    Profile,
    User,
    user_interests,
)

# --- knobs you might actually change -------------------------------------

CENTER = (40.6552, -74.0069)  # Sunset Park, Brooklyn (lat, lng)
SCATTER_KM = 1.6              # events land within this radius of CENTER
DEMO_PASSWORD = "password-123"
random.seed(42)               # reproducible scatter/choices across runs

password_helper = PasswordHelper()
NOW = datetime.now(timezone.utc)

# --- demo people (bios echo the project's user personas) -----------------
# (email_prefix, display_name, avatar_emoji, bio, open_to_help, interest_slugs)
PEOPLE = [
    ("dylan", "Dylan", "🧭",
     "New to the neighborhood and looking to meet people. Big believer that "
     "shared experiences teach us the most.",
     False, ["outdoors-nature", "games", "music"]),
    ("bob", "Bob", "🏛️",
     "I run programs at the community center — rec, education, and social. "
     "Always trying to reflect what the neighborhood actually wants.",
     True, ["volunteering", "local-history", "seniors"]),
    ("mitch", "Mitch", "🎒",
     "College student. Straight to class, straight home — but I tidy up, pick "
     "up litter, and show up. Doing a little still matters.",
     True, ["books-reading", "volunteering", "technology"]),
    ("eleanor", "Eleanor", "🌷",
     "Living independently and happy to. Could use a hand now and then, and "
     "I'd love a little more company.",
     False, ["gardening", "cooking-food", "seniors"]),
    ("priya", "Priya", "🎨",
     "Watercolors, community murals, and anything that gets neighbors making "
     "things together.",
     True, ["arts-crafts", "kids-family"]),
    ("marcus", "Marcus", "🏀",
     "Pickup basketball organizer and weekend runner. If you're new, come "
     "play — nobody's keeping score.",
     True, ["sports-fitness", "health-wellness"]),
    ("wei", "Wei", "🍜",
     "I cook for a crowd whenever I can. Dumpling nights are my love language.",
     True, ["cooking-food", "kids-family"]),
    ("aisha", "Aisha", "📚",
     "Librarian by trade, book-club evangelist by choice. Also fostering two "
     "very opinionated cats.",
     True, ["books-reading", "pets", "local-history"]),
    ("tomas", "Tomás", "🔧",
     "Handy with tools and happy to lend them. Ask me before you rent a drill.",
     True, ["home-repair-diy", "gardening"]),
    ("nina", "Nina", "🎻",
     "Music teacher. Trying to start a casual porch-music night this summer.",
     True, ["music", "arts-crafts"]),
    ("sam", "Sam", "🌱",
     "Community garden plot #14. Tomatoes are thriving; my basil is a tragedy.",
     True, ["gardening", "outdoors-nature", "cooking-food"]),
    ("greta", "Greta", "🐕",
     "Dog walker and unofficial block historian. I know which stoop has the "
     "friendliest cat.",
     False, ["pets", "outdoors-nature", "local-history"]),
]

# --- demo organizations ----------------------------------------------------
# Local institutions around Sunset Park. The verified/unverified split mirrors
# the real rule in app/core/orgs.py: an address on a domain that can't be
# casually registered (.gov, k12.*.us) auto-verifies once confirmed, while a
# .org waits for a moderator — so the two states are both visible in the demo.
# (email_prefix, domain, display_name, emoji, category, website, verified, bio)
ORGANIZATIONS = [
    ("library", "ci.brooklyn.gov", "Sunset Park Library", "📚", "library",
     "https://www.bklynlibrary.org/locations/sunset-park", True,
     "Your branch on 4th Ave. Story times, free wifi, meeting rooms, and a "
     "very patient tech help desk."),
    ("parks", "ci.brooklyn.gov", "NYC Parks — Sunset Park", "🌳", "parks",
     "https://www.nycgovparks.org/parks/sunset-park", True,
     "The 24-acre park, the pool, and the best view of the harbour in "
     "Brooklyn. We run volunteer days most weekends."),
    ("ps371", "ps371.k12.ny.us", "P.S. 371 Lillian L. Rashkis", "🏫", "school",
     "https://www.schools.nyc.gov", True,
     "Neighbourhood elementary school. Always looking for reading buddies and "
     "hands for the spring fair."),
    ("mutualaid", "sunsetparkmutualaid.org", "Sunset Park Mutual Aid", "🧺",
     "nonprofit", "https://sunsetparkmutualaid.org", False,
     "Neighbours feeding neighbours since 2020. Weekly pantry, coat drives, "
     "and a phone tree for anyone who needs one."),
    ("trinity", "trinitysunset.org", "Trinity Lutheran Fellowship", "⛪",
     "faith", "https://trinitysunset.org", False,
     "Doors open to everyone. We host the Tuesday supper and lend the hall "
     "out for neighbourhood meetings."),
]

# Volunteer shifts an organization recruits for — the org counterpart to a
# neighbour's help request. (org_prefix, title, description, interest_slugs,
# capacity)
VOLUNTEER_WORK = [
    ("library", "Shelve returns with us",
     "Two hours of quiet, satisfying sorting. We'll show you the system, and "
     "there's coffee.", ["books-reading", "volunteering"], 6),
    ("library", "Senior tech help desk",
     "Sit with a neighbour and their phone. Patience matters far more than "
     "technical skill.", ["technology", "seniors"], 4),
    ("library", "Toddler story time helper",
     "Wrangle cushions, hand out instruments, read a page or two. Chaos, but "
     "the good kind.", ["kids-family", "books-reading"], 3),
    ("parks", "Saturday park cleanup",
     "Meet at the 5th Ave entrance. Bags, gloves and grabbers provided — just "
     "bring sturdy shoes.", ["outdoors-nature", "volunteering"], None),
    ("parks", "Prep the community garden beds",
     "Turning soil and laying compost before the autumn planting. Tools "
     "supplied, no experience needed.", ["gardening", "outdoors-nature"], 12),
    ("parks", "Tree stewardship walk",
     "Learn to mulch and water the street trees, then take a block of your "
     "own if you'd like.", ["outdoors-nature", "volunteering"], 10),
    ("ps371", "Reading buddy, Tuesday mornings",
     "Twenty minutes each with three second-graders. Background check needed "
     "for regulars — drop-ins welcome to observe.", ["books-reading", "kids-family"], 8),
    ("ps371", "Spring fair setup crew",
     "Tables, bunting, and one slightly temperamental popcorn machine.",
     ["kids-family", "volunteering"], 15),
    ("mutualaid", "Pack the weekly food pantry",
     "Assembly line, music on, done in two hours. Kids welcome alongside an "
     "adult.", ["cooking-food", "volunteering"], 20),
    ("mutualaid", "Coat drive sorting",
     "Sizing, checking zips, boxing by age. Bring a coat you've outgrown "
     "while you're at it.", ["volunteering"], 10),
    ("mutualaid", "Phone tree check-in shift",
     "Ring six neighbours who live alone and have a proper chat. Script "
     "provided if it helps.", ["seniors", "volunteering"], 6),
    ("trinity", "Tuesday supper kitchen",
     "Chop, serve, wash up, eat with everyone. The hall seats sixty and "
     "usually fills.", ["cooking-food", "volunteering"], 8),
    ("trinity", "Set up the neighbourhood meeting hall",
     "Chairs and a projector before the tenants' association meets.",
     ["volunteering"], 4),
]

# Gatherings hosted by organizations — open invitations, not volunteer shifts.
ORG_GATHERINGS = [
    ("library", "Library book club: Brooklyn stories",
     "This month a novel set six blocks from here. Copies held at the desk.",
     ["books-reading", "local-history"], 20),
    ("parks", "Sunset yoga on the north lawn",
     "Free, all levels, bring a towel. Cancelled if it rains.",
     ["health-wellness", "outdoors-nature"], 30),
    ("trinity", "Community potluck supper",
     "Bring a dish if you can, come anyway if you can't.",
     ["cooking-food", "kids-family"], 60),
]


# --- demo events -----------------------------------------------------------
# (kind, title, description, interest_slugs, capacity)
GATHERINGS = [
    ("gathering", "Board games in the park",
     "Casual games on blankets by the 5th Ave entrance. Beginners welcome, "
     "we'll teach you.", ["games", "outdoors-nature"], 12),
    ("gathering", "Sunday morning group run",
     "Easy 5k, nobody left behind. Meet at the park steps.",
     ["sports-fitness", "health-wellness"], None),
    ("gathering", "Dumpling night",
     "Come fold and eat. Bring a container to take some home.",
     ["cooking-food", "kids-family"], 10),
    ("gathering", "Porch music night",
     "Bring an instrument or just your ears. Acoustic only.",
     ["music"], None),
    ("gathering", "Neighborhood book club: local history pick",
     "This month: a history of the waterfront. Newcomers always welcome.",
     ["books-reading", "local-history"], 15),
    ("gathering", "Community garden work day",
     "Weeding, watering, and planting the fall beds. Tools provided.",
     ["gardening", "volunteering", "outdoors-nature"], None),
    ("gathering", "Watercolor in the park",
     "Loose, low-pressure painting session. Supplies to share.",
     ["arts-crafts"], 8),
    ("gathering", "Coffee chat for newcomers",
     "New to the area? Gentle, friendly, no agenda. Just come say hi.",
     ["seniors"], None),
    ("gathering", "Pickup basketball",
     "Half-court, rotating teams, all skill levels.",
     ["sports-fitness"], None),
    ("gathering", "Kids' craft afternoon",
     "Bring the little ones for glue, glitter, and mild chaos.",
     ["kids-family", "arts-crafts"], 20),
    ("gathering", "Evening stroll & birdwatching",
     "Slow loop around the park green. Binoculars optional.",
     ["outdoors-nature", "seniors"], None),
    ("gathering", "Repair café: bring something broken",
     "Lamps, chairs, small electronics — we'll try to fix it together.",
     ["home-repair-diy", "volunteering"], None),
    ("gathering", "Community potluck",
     "Bring a dish that means something to you. Big tables, open seats.",
     ["cooking-food", "kids-family"], 30),
    ("gathering", "Tech help hour for seniors",
     "Phones, tablets, and 'why is it doing that'. Patient volunteers on hand.",
     ["technology", "seniors"], None),
]

HELP_REQUESTS = [
    ("help_request", "Help moving a bookshelf",
     "Solid oak, one flight of stairs. Two people and 20 minutes should do it.",
     ["home-repair-diy"], None),
    ("help_request", "Ride to the pharmacy Thursday",
     "Round trip, about 15 minutes each way. I'll have coffee ready.",
     ["seniors"], None),
    ("help_request", "Someone to teach me my new phone",
     "I just want to video-call my grandkids without the panic.",
     ["technology", "seniors"], None),
    ("help_request", "Weekend hand in the garden",
     "Beds need turning before the fall planting. I'll share the harvest.",
     ["gardening", "outdoors-nature"], None),
    ("help_request", "Dog walker while I recover",
     "Sprained my ankle. Gentle old lab, loves everyone, two weeks.",
     ["pets"], None),
    ("help_request", "Help assembling flat-pack furniture",
     "A wardrobe and a desk. I have the tools, just need an extra set of hands.",
     ["home-repair-diy"], None),
    ("help_request", "Proofread a scholarship essay",
     "First in my family to apply — would love a second pair of eyes.",
     ["books-reading"], None),
    ("help_request", "Carry groceries up on Sundays",
     "Fourth floor, no elevator. A friendly regular would be a godsend.",
     ["seniors", "volunteering"], None),
    ("help_request", "Jump-start / car won't turn over",
     "Battery's dead in the lot on 44th. Have cables, need a car.",
     ["home-repair-diy"], None),
    ("help_request", "Cat-sitting backup for a weekend",
     "Two cats, very independent. Just feeding and company Sat-Sun.",
     ["pets"], None),
]


def scatter(center):
    """A random point within ~SCATTER_KM of center. 1 deg lat ~= 111 km;
    longitude degrees shrink by cos(latitude)."""
    max_dlat = SCATTER_KM / 111.0
    max_dlng = SCATTER_KM / (111.0 * math.cos(math.radians(center[0])))
    return (
        center[0] + random.uniform(-max_dlat, max_dlat),
        center[1] + random.uniform(-max_dlng, max_dlng),
    )


async def main() -> None:
    if "_dev" not in settings.database_url and "--force" not in sys.argv:
        sys.exit(
            "Refusing to seed: DATABASE_URL does not look like a dev database.\n"
            "Pass --force only if you are certain."
        )

    # 1. Clean slate. CASCADE clears profiles, participants, connections,
    #    messages, blocks, reports, access_tokens, and the join tables.
    #    Interests (owned by a migration) are untouched.
    async with engine.begin() as conn:
        # import_areas goes too: it's the ledger of which map tiles have already
        # been imported, and truncating events without it would leave tiles
        # marked 'done' for work that no longer exists — the map would show no
        # imported events until FRESH_FOR (24h) elapsed.
        await conn.execute(
            text("TRUNCATE users, events, communities, import_areas CASCADE")
        )

    async with AsyncSessionLocal() as session:
        interests = {
            i.slug: i for i in (await session.scalars(select(Interest))).all()
        }
        if not interests:
            sys.exit(
                "No interests found — run `alembic upgrade head` first so the "
                "starter interests are seeded."
            )

        # 2. The community everyone belongs to. osm_ref matches the real
        # OpenStreetMap node so that a user picking "Sunset Park" from the
        # live neighborhood list reuses this row instead of duplicating it.
        community = Community(
            name="Sunset Park",
            slug="sunset-park",
            osm_ref="node/3343148003",
            center=wkt_point(*CENTER),
        )
        session.add(community)
        await session.flush()  # assigns community.id

        # 3. Users + profiles.
        users = {}
        hashed = password_helper.hash(DEMO_PASSWORD)
        for prefix, name, emoji, bio, open_to_help, slugs in PEOPLE:
            user = User(
                email=f"{prefix}@example.com",
                hashed_password=hashed,
                # People never carry the organization badge; the ORGANIZATIONS
                # below do.
            )
            session.add(user)
            await session.flush()
            session.add(
                Profile(
                    user_id=user.id,
                    community_id=community.id,
                    display_name=name,
                    avatar_key=emoji,
                    bio=bio,
                    open_to_help=open_to_help,
                    show_attending=True,
                )
            )
            if slugs:
                await session.execute(
                    user_interests.insert(),
                    [{"user_id": user.id, "interest_id": interests[s].id} for s in slugs],
                )
            users[prefix] = user

        user_list = list(users.values())

        # 3b. Organization accounts. Verified ones use a gated domain, matching
        # the real rule; the .org ones sit unverified as they would pending a
        # moderator's check.
        orgs = {}
        for (prefix, domain, name, emoji, category, website,
             verified, bio) in ORGANIZATIONS:
            user = User(
                email=f"{prefix}@{domain}",
                hashed_password=hashed,
                org_verified=verified,
                # These signed up and clicked the link; that's what earns the
                # badge for a gated domain.
                email_confirmed_at=NOW,
            )
            session.add(user)
            await session.flush()
            session.add(
                Profile(
                    user_id=user.id,
                    community_id=community.id,
                    display_name=name,
                    avatar_key=emoji,
                    bio=bio,
                    account_type="organization",
                    org_category=category,
                    org_website=website,
                    org_phone=f"(718) 555-{random.randint(1000, 9999)}",
                    org_address=f"{random.randint(100, 899)} 4th Ave, Brooklyn",
                    org_contact_name=random.choice(
                        ["Bob Ellis", "Dana Whitfield", "Marisol Vega"]
                    ),
                    org_contact_role=random.choice(
                        ["Programs Director", "Branch Manager", "Volunteer Coordinator"]
                    ),
                    show_attending=True,
                )
            )
            orgs[prefix] = user

        # 4. Events, scattered in space and time, hosted round-robin.
        all_events = GATHERINGS + HELP_REQUESTS
        random.shuffle(all_events)
        created = []
        for idx, (kind, title, desc, slugs, capacity) in enumerate(all_events):
            host = user_list[idx % len(user_list)]
            lat, lng = scatter(CENTER)
            starts = NOW + timedelta(
                days=random.randint(1, 20), hours=random.randint(0, 12)
            )
            # ~15% community-only, ~8% private, rest public.
            roll = random.random()
            visibility = "community" if roll < 0.15 else "private" if roll < 0.23 else "public"
            # A single category tag drives the map pin's icon — use the first
            # of each event's listed slugs.
            tag_id = interests[slugs[0]].id if slugs else None
            event = Event(
                kind=kind,
                host_id=host.id,
                community_id=community.id,
                tag_id=tag_id,
                title=title,
                description=desc,
                location=wkt_point(lat, lng),
                address=f"{random.randint(100, 899)} {random.randint(38, 52)}th St, Brooklyn",
                starts_at=starts,
                ends_at=starts + timedelta(hours=2),
                visibility=visibility,
                capacity=capacity,
            )
            session.add(event)
            await session.flush()
            created.append((event, host, capacity))

        # 4b. What the organizations posted. Always public — an institution
        # recruiting volunteers has no reason to hide it.
        org_posts = [("volunteer_work", *row) for row in VOLUNTEER_WORK] + [
            ("gathering", *row) for row in ORG_GATHERINGS
        ]
        random.shuffle(org_posts)
        for kind, org_prefix, title, desc, slugs, capacity in org_posts:
            host = orgs[org_prefix]
            lat, lng = scatter(CENTER)
            starts = NOW + timedelta(
                days=random.randint(1, 21), hours=random.randint(0, 10)
            )
            event = Event(
                kind=kind,
                host_id=host.id,
                community_id=community.id,
                tag_id=interests[slugs[0]].id if slugs else None,
                title=title,
                description=desc,
                location=wkt_point(lat, lng),
                address=f"{random.randint(100, 899)} {random.randint(38, 52)}th St, Brooklyn",
                starts_at=starts,
                ends_at=starts + timedelta(hours=random.choice([2, 3])),
                visibility="public",
                capacity=capacity,
            )
            session.add(event)
            await session.flush()
            created.append((event, host, capacity))

        # 5. RSVPs, so events show non-zero attendance. Never the host,
        #    never over capacity.
        for event, host, capacity in created:
            others = [u for u in user_list if u.id != host.id]
            random.shuffle(others)
            seats = capacity if capacity is not None else 6
            going = others[: min(random.randint(1, 5), seats)]
            for u in going:
                session.add(
                    EventParticipant(event_id=event.id, user_id=u.id, status="going")
                )
            for u in others[len(going):len(going) + random.randint(0, 2)]:
                session.add(
                    EventParticipant(event_id=event.id, user_id=u.id, status="maybe")
                )

        # 6. A few accepted connections so the social graph isn't empty.
        pairs = [
            ("dylan", "marcus"), ("dylan", "wei"), ("eleanor", "greta"),
            ("eleanor", "bob"), ("mitch", "aisha"), ("priya", "nina"),
            ("sam", "tomas"),
        ]
        for a, b in pairs:
            session.add(
                Connection(
                    requester_id=users[a].id,
                    addressee_id=users[b].id,
                    status="accepted",
                    responded_at=NOW,
                )
            )

        # 6b. Follows, so the Organizations tab isn't empty. Everyone follows
        # the library and the park; the rest get a scattering.
        for person in user_list:
            followed = {"library", "parks"}
            followed.update(
                random.sample(
                    ["ps371", "mutualaid", "trinity"], random.randint(0, 2)
                )
            )
            for org_prefix in followed:
                session.add(
                    OrgFollow(follower_id=person.id, org_id=orgs[org_prefix].id)
                )

        # 6c. A few org_event notifications, as the fan-out would have produced
        # when these were posted — so the alerts page shows the feature working.
        org_events = [
            (event, host) for event, host, _ in created
            if host.id in {o.id for o in orgs.values()}
        ]
        for event, host in random.sample(org_events, min(4, len(org_events))):
            follower_ids = (
                await session.scalars(
                    select(OrgFollow.follower_id).where(OrgFollow.org_id == host.id)
                )
            ).all()
            for follower_id in random.sample(
                list(follower_ids), min(3, len(follower_ids))
            ):
                session.add(
                    Notification(
                        user_id=follower_id,
                        type="org_event",
                        actor_id=host.id,
                        event_id=event.id,
                    )
                )

        await session.commit()

    # 7. Report.
    print("Seeded the Sunset Park demo neighborhood:")
    print(f"  {len(PEOPLE)} people, {len(ORGANIZATIONS)} organizations")
    print(f"  {len(GATHERINGS)} gatherings + {len(HELP_REQUESTS)} help requests "
          f"+ {len(VOLUNTEER_WORK)} volunteer shifts + {len(ORG_GATHERINGS)} org gatherings")
    print(f"  center: {CENTER} (deny the browser location prompt to land here)")
    print(f"\n  All accounts use password: {DEMO_PASSWORD}")
    print("\n  People:")
    for prefix, name, *_ in PEOPLE:
        print(f"    {prefix}@example.com   ({name})")
    print("\n  Organizations (log in to post volunteer work):")
    for prefix, domain, name, _emoji, category, _site, verified, _bio in ORGANIZATIONS:
        mark = "verified" if verified else "unverified"
        print(f"    {prefix}@{domain}".ljust(42) + f"{name} — {category}, {mark}")


if __name__ == "__main__":
    asyncio.run(main())
