"""Import all models here so Alembic autogenerate can discover them via Base.metadata."""
from app.models.block import Block
from app.models.community import Community
from app.models.connection import Connection
from app.models.event import Event, EventMessage, EventParticipant
from app.models.interest import EventInterest, Interest, UserInterest
from app.models.profile import Profile
from app.models.report import Report
from app.models.user import User

__all__ = [
    "Block",
    "Community",
    "Connection",
    "Event",
    "EventMessage",
    "EventParticipant",
    "EventInterest",
    "Interest",
    "UserInterest",
    "Profile",
    "Report",
    "User",
]
