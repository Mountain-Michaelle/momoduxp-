from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from shared.models.users import User


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()
