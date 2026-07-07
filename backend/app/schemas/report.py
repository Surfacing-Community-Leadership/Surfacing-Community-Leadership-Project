from pydantic import BaseModel
from uuid import UUID


class ReportCreateRequest(BaseModel):
    reported_user_id: UUID | None = None
    reported_event_id: UUID | None = None
    reason: str
    details: str | None = None


class ReportCreateResponse(BaseModel):
    id: UUID
    status: str
