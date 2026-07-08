import uuid

from pydantic import BaseModel, Field, model_validator


class ReportCreate(BaseModel):
    reported_user_id: uuid.UUID | None = None
    reported_event_id: uuid.UUID | None = None
    reason: str = Field(min_length=1, max_length=200)
    details: str | None = Field(None, max_length=5000)

    @model_validator(mode="after")
    def must_target_something(self):
        if self.reported_user_id is None and self.reported_event_id is None:
            raise ValueError("A report must target a user or an event")
        return self


class ReportRead(BaseModel):
    id: uuid.UUID
    status: str
