"""SQLAdmin admin panel, mounted at /admin.

Login is gated to active superusers. Promote an account with:
    .venv/bin/python scripts/make_admin.py you@example.com
"""

from fastapi_users.password import PasswordHelper
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
from starlette.requests import Request

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models import Community, Event, Interest, Profile, Report, User

password_helper = PasswordHelper()


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        email = form.get("username", "")
        password = form.get("password", "")
        async with AsyncSessionLocal() as session:
            user = await session.scalar(select(User).where(User.email == email))
        if user is None or not user.is_superuser or not user.is_active:
            password_helper.hash(password)  # burn time anyway: no user-exists oracle
            return False
        verified, _ = password_helper.verify_and_update(password, user.hashed_password)
        if not verified:
            return False
        request.session.update({"admin_user_id": str(user.id)})
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "admin_user_id" in request.session


class UserAdmin(ModelView, model=User):
    name_plural = "Users"
    icon = "fa-solid fa-user"
    column_list = [User.email, User.is_active, User.is_verified, User.is_superuser, User.created_at]
    column_searchable_list = [User.email]
    column_details_exclude_list = [User.hashed_password]
    form_excluded_columns = [User.hashed_password, User.created_at]
    can_create = False  # accounts are made through the app, never by hand


class ProfileAdmin(ModelView, model=Profile):
    name_plural = "Profiles"
    icon = "fa-solid fa-id-card"
    column_list = [Profile.display_name, Profile.user_id, Profile.community_id]
    column_searchable_list = [Profile.display_name]
    form_excluded_columns = [Profile.created_at, Profile.updated_at]
    can_create = False


class CommunityAdmin(ModelView, model=Community):
    name_plural = "Communities"
    icon = "fa-solid fa-map"
    column_list = [Community.name, Community.slug, Community.created_at]
    # PostGIS geography has no form widget; set centers via SQL for now.
    form_excluded_columns = [Community.center, Community.created_at]


class InterestAdmin(ModelView, model=Interest):
    name_plural = "Interests"
    icon = "fa-solid fa-tag"
    column_list = [Interest.name, Interest.slug]


class EventAdmin(ModelView, model=Event):
    name_plural = "Events"
    icon = "fa-solid fa-calendar"
    column_list = [Event.title, Event.kind, Event.status, Event.visibility, Event.starts_at]
    column_searchable_list = [Event.title]
    form_excluded_columns = [Event.location, Event.created_at, Event.updated_at]
    can_create = False  # events belong to hosts; admins moderate, not author


class ReportAdmin(ModelView, model=Report):
    name_plural = "Reports (moderation queue)"
    icon = "fa-solid fa-flag"
    column_list = [Report.status, Report.reason, Report.reported_user_id, Report.reported_event_id, Report.created_at]
    form_columns = [Report.status, Report.resolved_at, Report.resolved_by]
    can_create = False
    can_delete = False  # the queue is an audit trail; resolve, don't erase


def mount_admin(app) -> Admin:
    admin = Admin(
        app,
        engine,
        authentication_backend=AdminAuth(secret_key=settings.secret_key),
    )
    for view in (UserAdmin, ProfileAdmin, CommunityAdmin, InterestAdmin, EventAdmin, ReportAdmin):
        admin.add_view(view)
    return admin
