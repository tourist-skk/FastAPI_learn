from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from models.news import Category,News
from config.db_conf import get_db
from sqlalchemy import select,func,update
from fastapi import HTTPException
from cache.news_cache import get_news_categories,set_news_categories
from fastapi.encoders import jsonable_encoder



# 缓存中获取新闻分类列表
async def get_category_list(
        skip: int = 0,
        limits: int = 100,
        db: AsyncSession = Depends(get_db)
    ):
    # 先从缓存中获取
    cached_categories = await get_news_categories()
    if cached_categories is not None:
        return cached_categories
    # 如果没有查出缓存，从数据库中查询，然后写入缓存
    stmt = select(Category).offset(skip).limit(limits)
    result = await db.execute(stmt)
    cache_categories = result.scalars().all() # ORM对象列表，内部是ROW对象
    #cached_categories = result.mappings().all()
    if cache_categories is not None:
        cached_categories = jsonable_encoder(cache_categories)
        # 写入缓存
        await set_news_categories(cached_categories, expire=7200)
    return cached_categories

async def get_category_news_list(
        category_id: int,
        skip: int = 0,
        page_size: int = 10,
        db: AsyncSession = Depends(get_db)
    ):
    stmt = select(News).where(News.category_id == category_id).offset(skip).limit(page_size)
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_category_news_count(
        category_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    stmt = select(func.count(News.id)).where(News.category_id == category_id)
    result = await db.execute(stmt)
    return result.scalar_one()

# 根据ID获取新闻详情
async def get_news_detail(
        news_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    stmt = select(News).where(News.id == news_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

# 根据ID获取推荐新闻
# 但实际上获取推荐新闻，不需要获得完整的新闻数据，只需要其中一部分
async def get_recommend_news(
        news_id: int,
        db: AsyncSession = Depends(get_db),
        limit: int = 5
    ):
    # 默认是升序,desc表示降序排序
    news_one = await get_news_detail(news_id, db)
    stmt = select(News).where(
        News.id != news_id ,
        News.category_id == news_one.category_id
    ).order_by(News.views.desc(),News.publish_time.desc()).limit(limit)# desc:降序排序
    result = await db.execute(stmt)
    related_news = result.scalars().all()
    #return result.scalars().all()
    # 返回列表推导式,只返回新闻ID,标题,点击量,发布时间,图片URL,分类ID,内容,作者
    # 也可以返回响应模型
    return [{"id": item.id, "title": item.title, "views": item.views, "publishTime": item.publish_time, "image": item.image, "categoryId": item.category_id, "content": item.content, "author": item.author} for item in related_news]

async def update_news_views(
        news_id: int,
        db: AsyncSession = Depends(get_db)
    ):
    #news_one = await db.get(News, news_id)
    result = await db.execute(update(News).where(News.id == news_id).values(views=News.views + 1))
    await db.commit()

    return result.rowcount
