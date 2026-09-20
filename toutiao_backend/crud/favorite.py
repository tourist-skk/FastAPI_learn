from fastapi import Depends, HTTPException
from models.favorite import Favorite
from config.db_conf import get_db
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession



async def is_news_favorite(
        user_id: int,
        news_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    stmt = select(Favorite).where(Favorite.user_id == user_id, Favorite.news_id == news_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def add_favorite(
        news_id: int,
        user_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    # existing = await db.scalar(
    #     select(Favorite).where(Favorite.user_id == user_id, Favorite.news_id == news_id)
    # )
    # if existing is not None:
    #     return existing

    favorite = Favorite(
        user_id=user_id,
        news_id=news_id,
    )
    db.add(favorite)
    await db.flush()
    #await db.refresh(favorite)
    return favorite


async def remove_favorite(
        news_id: int,
        user_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    stmt = delete(Favorite).where(Favorite.user_id == user_id, Favorite.news_id == news_id)
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount > 0
