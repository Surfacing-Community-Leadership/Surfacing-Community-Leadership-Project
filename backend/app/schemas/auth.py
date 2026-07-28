import uuid
from typing import Literal

from fastapi_users import schemas as fu_schemas
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.profile import ORG_CATEGORIES


class UserCreate(fu_schemas.BaseUserCreate):
    """Internal shape handed to fastapi-users' UserManager."""


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str = Field(min_length=1, max_length=80)

    # --- organization signup (optional) ----------------------------------
    # Declaring "organization" is self-service; it does NOT grant the ✓ badge.
    # See app/core/orgs.py for how verification is actually decided.
    account_type: Literal["person", "organization"] = "person"
    org_category: str | None = None  # validated against ORG_CATEGORIES below
    org_website: str | None = Field(None, max_length=300)
    org_phone: str | None = Field(None, max_length=40)
    org_address: str | None = Field(None, max_length=300)
    org_contact_name: str | None = Field(None, max_length=120)
    org_contact_role: str | None = Field(None, max_length=120)

    @model_validator(mode="after")
    def _org_needs_evidence(self):
        if self.account_type != "organization":
            # Keep a personal signup clean — ignore any stray org fields.
            self.org_category = None
            self.org_website = None
            self.org_phone = None
            self.org_address = None
            self.org_contact_name = None
            self.org_contact_role = None
            return self
        if self.org_category not in ORG_CATEGORIES:
            raise ValueError(
                "Pick an organization type: " + ", ".join(ORG_CATEGORIES)
            )
        # The website is what an admin checks when the domain isn't gated.
        if not (self.org_website or "").strip():
            raise ValueError("An organization needs a website we can check")
        return self


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    # The organization badge — not email confirmation. See models/user.py.
    is_verified: bool


class UserMe(UserRead):
    is_superuser: bool
    email_confirmed: bool

    @classmethod
    def from_user(cls, user) -> "UserMe":
        return cls(
            id=user.id,
            email=user.email,
            is_verified=user.is_verified,
            is_superuser=user.is_superuser,
            email_confirmed=user.email_confirmed_at is not None,
        )


class ConfirmEmailPayload(BaseModel):
    token: str


class ConfirmEmailResult(BaseModel):
    email: str
    already_confirmed: bool
    # True when confirming this address also earned the organization badge.
    organization_verified: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
