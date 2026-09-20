from fastapi import Depends
from models.favorite import Favorite
from config.db_conf import get_db
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession



async def is_news_favorite(
        user_id: int,
        news_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    stmt = select(Favorite).where(Favorite.user_id == user_id, Favorite.news_id == news_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None