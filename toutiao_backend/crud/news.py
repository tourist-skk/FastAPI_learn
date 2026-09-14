from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from models.news import Category
from config.db_conf import get_db
from sqlalchemy import select

async def get_category_list(
        skip: int = 0,
        limits: int = 100,
        db: AsyncSession = Depends(get_db)
    ):
    stmt = select(Category).offset(skip).limit(limits)
    result = await db.execute(stmt)
    return result.scalars().all()