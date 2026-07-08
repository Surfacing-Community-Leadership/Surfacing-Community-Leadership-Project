# Import every model here so that defining the classes registers their
# tables in Base.metadata — this is what Alembic autogenerate diffs against.
from app.models.user import User

__all__ = ["User"]
