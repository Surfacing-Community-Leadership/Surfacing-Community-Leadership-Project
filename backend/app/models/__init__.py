# Import every model here so that defining the classes registers their
# tables in Base.metadata — this is what Alembic autogenerate diffs against.
from app.models.access_token import AccessToken
from app.models.assistant_turn import AssistantTurn
from app.models.block import Block
from app.models.community import Community
from app.models.connection import Connection
from app.models.event import Event
from app.models.flyer_generation import FlyerGeneration
from app.models.help_thanks import HelpThanks
from app.models.import_area import ImportArea
from app.models.interest import Interest, user_interests
from app.models.message import EventMessage
from app.models.notice import Notice, NoticeReply, NoticeStar
from app.models.notification import Notification
from app.models.oauth_account import OAuthAccount
from app.models.org_follow import OrgFollow
from app.models.participant import EventParticipant
from app.models.profile import Profile
from app.models.report import Report
from app.models.seed_state import SeedState
from app.models.user import User

__all__ = [
    "AccessToken",
    "AssistantTurn",
    "Block",
    "Community",
    "Connection",
    "Event",
    "EventMessage",
    "EventParticipant",
    "FlyerGeneration",
    "HelpThanks",
    "ImportArea",
    "Interest",
    "Notice",
    "NoticeReply",
    "NoticeStar",
    "Notification",
    "OAuthAccount",
    "OrgFollow",
    "Profile",
    "Report",
    "SeedState",
    "User",
    "user_interests",
]
