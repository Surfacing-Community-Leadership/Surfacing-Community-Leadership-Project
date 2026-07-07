from pydantic import BaseModel
from uuid import UUID


class InterestResponse(BaseModel):
    id: UUID
    name: str
    slug: str
