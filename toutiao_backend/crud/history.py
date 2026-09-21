from config.db_conf import get_db
from sqlalchemy import select, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException
from models.history import History
from models.news import News

async def add_history(
        user_id: int,
        news_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    # 添加浏览记录。如果已经存在，更新浏览时间；否则，创建新记录。
    result = await db.execute(
        select(History).where(
            and_(
                History.user_id == user_id,
                History.news_id == news_id
            )
        )
    )
    # 不能直接在execute中使用scalar_one_or_none，因为会返回一个Coroutine对象，需要等待执行完成
    existing_history = result.scalar_one_or_none()
    if existing_history:
        existing_history.view_time = func.now()
        await db.flush()
        return existing_history
    history = History(
        user_id=user_id,
        news_id=news_id,
    )
    db.add(history)
    await db.flush()
    return history

async def get_count_history(
        user_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    # 获取用户浏览记录数量
    stmt = (
        select(func.count(History.id))
        .select_from(History)
        .where(History.user_id == user_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()



async def get_history_list(
        user_id: int,
        page: int = 1,
        page_size: int = 10,
        db: AsyncSession = Depends(get_db)
    ):
    # 获取用户浏览记录
    stmt = (
        select(
            News.id,
            News.title,
            News.description,
            News.image,
            News.author,
            News.publish_time,
            News.category_id,
            News.views,
            History.view_time
        )
        .select_from(News)
        .join(History, and_(History.user_id == user_id, History.news_id == News.id))
        .order_by(History.view_time.desc())
    )
    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    return result.mappings().all()

# 删除浏览记录，参数是新闻id和用户id
async def delete_history(
        news_id: int,
        user_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    # 删除浏览记录
    stmt = delete(History).where(History.news_id == news_id, History.user_id == user_id)
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="浏览记录不存在")
    await db.flush()
    return result.rowcount > 0

async def clear_history(
        user_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    # 清空用户浏览记录
    stmt = delete(History).where(History.user_id == user_id)
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="浏览记录不存在")
    await db.flush()
    return result.rowcount
