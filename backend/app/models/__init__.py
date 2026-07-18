# Import every model here so that defining the classes registers their
# tables in Base.metadata — this is what Alembic autogenerate diffs against.
from app.models.access_token import AccessToken
from app.models.block import Block
from app.models.community import Community
from app.models.connection import Connection
from app.models.event import Event
from app.models.interest import Interest, user_interests
from app.models.message import EventMessage
from app.models.participant import EventParticipant
from app.models.profile import Profile
from app.models.report import Report
from app.models.user import User

__all__ = [
    "AccessToken",
    "Block",
    "Community",
    "Connection",
    "Event",
    "EventMessage",
    "EventParticipant",
    "Interest",
    "Profile",
    "Report",
    "User",
    "user_interests",
]
