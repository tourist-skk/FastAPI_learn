from fastapi import Depends, HTTPException
from models.favorite import Favorite
from models.news import News
from config.db_conf import get_db
from sqlalchemy import select, delete, and_, func
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

# 移除收藏
async def remove_favorite(
        news_id: int,
        user_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    stmt = delete(Favorite).where(Favorite.user_id == user_id, Favorite.news_id == news_id)
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount > 0

# 获取收藏列表
async def get_favorite_list(
        user_id: int,
        page: int,
        page_size: int,
        db: AsyncSession = Depends(get_db)
    ):
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
            Favorite.created_at,
        )
        .select_from(News)
        .join(Favorite, and_(
            Favorite.news_id == News.id,
            Favorite.user_id == user_id,
        ))# 为什么不能写order_by(Favorite.created_at.desc)
        .order_by(Favorite.created_at.desc())
    )
    offset = (page - 1) * page_size
    limit = page_size
    result = await db.execute(stmt.offset(offset).limit(limit))
    # scalars() 只能用于「单列 / 单个实体」的结果。你现在 select 了 8 列，每行是一个 Row（含多个字段），调用 .scalars() 会抛出 InvalidRequestError。
    # 如果直接返回result.all()，会返回一个 Row 对象列表，每个 Row 对象是一个元组,包含 8 个字段。
    return result.mappings().all()

async def get_favorite_count(
        user_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    stmt = select(func.count(Favorite.id)).where(Favorite.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one()


async def clear_favorite(
        user_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    stmt = delete(Favorite).where(Favorite.user_id == user_id)
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount > 0, result.rowcount



# @router.get("/list")
# async def get_favorite_list(
#         page: int = Query(1, ge=1),
#         page_size: int = Query(10, ge=1, le=100, alias="pageSize"),
#         user: User = Depends(get_current_user),
#         db: AsyncSession = Depends(get_db)
# ):
#     rows, total = await favorite.get_favorite_list(db, user.id, page, page_size)
#     favorite_list = [{
#         **news.__dict__, 先属性访问在解包
#         "favorite_time": favorite_time,
#         "favorite_id": favorite_id
#     } for news, favorite_time, favorite_id in rows]
#     has_more = total > page * page_size
 
#     data = FavoriteListResponse(list=favorite_list, total=total, hasMore=has_more)
#     return success_response(message="获取收藏列表成功", data=data)