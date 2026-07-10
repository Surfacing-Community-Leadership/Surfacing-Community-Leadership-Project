"""Promote an existing user to superuser (grants /admin access).

Usage, from the backend/ directory:
    .venv/bin/python scripts/make_admin.py you@example.com
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import User


async def main(email: str) -> None:
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            sys.exit(f"No user with email {email!r} — register in the app first.")
        if user.is_superuser:
            print(f"{email} is already a superuser.")
            return
        user.is_superuser = True
        await session.commit()
        print(f"{email} is now a superuser and can log in at /admin.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1]))
