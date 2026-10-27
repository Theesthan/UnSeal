"""Case service: everything the routes and the Telegram bot do with a case.

This first slice only exports cases for FR-8; the full lifecycle lands next.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from unseal.db.models import Case, User


async def export_cases(session: AsyncSession, user: User) -> list[dict[str, Any]]:
    """FR-8: the user's cases as plain data (decrypted), for the export download."""
    found = await session.execute(select(Case).where(Case.user_id == user.id))
    return [
        {"id": case.id, "status": case.status, "language": case.language}
        for case in found.scalars()
    ]
