from fastapi import APIRouter,Query,Path
from crud import news
from config.db_conf import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends,HTTPException
from models.news import Category

# 创建APIRouter实例
# prefix: /api/news 路由前缀(API 接口规范标签)
# tags: news 路由标签(API 接口规范标签)
router = APIRouter(prefix="/api/news", tags=["news"])

# 
@router.get("/categories")
async def get_category_news(skip:int=0, limit:int=100, db: AsyncSession = Depends(get_db)):
    # 实际这里需要返回分页数据，因此需要查询数据库
    category_list = await news.get_category_list(skip, limit, db)
    return {
        "code": 200,
        "msg": "success",
        "data": category_list
    }

@router.get("/list")
async def get_category_news_list(
        category_id: int = Query(1, description="分类ID", alias="categoryId"), 
        page: int = Query(1, description="页码", alias="pageNum"), 
        page_size: int = Query(10, description="每页数量", alias="pageSize"), 
        db: AsyncSession = Depends(get_db)
    ):
    # 实际这里需要返回分页数据，因此需要查询数据库
    # 思路: 处理分页规则 -> 查询新闻列表 -> 计算总量 -> 计算是否还有更多(当前的起始点 + 当前页数量 < 总量)
    offset = (page - 1) * page_size
    news_list = await news.get_category_news_list(category_id, offset, page_size, db)
    news_count = await news.get_category_news_count(category_id, db)
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "list": news_list,
            "total": news_count,
            "has_more": news_count > offset + len(news_list)
        }
    }

# 需求: 响应结果必须是 当前新闻详情 + 增加1次点击量 + 相关推荐新闻
@router.get("/detail")
async def read_news_detail(
        news_id: int = Query(1, description="新闻ID", alias="id"),
        db: AsyncSession = Depends(get_db)
    ):
    # 实际这里需要返回新闻详情，因此需要查询数据库
    new_one = await news.get_news_detail(news_id, db)
    # if not new_one:
    #     raise HTTPException(status_code=404, detail="新闻不存在")
    # 需要更新该新闻的点击量
    views_count = await news.update_news_views(new_one.id, db)
    if views_count == 0:
        raise HTTPException(status_code=400, detail="更新点击量失败")
    # 需要获取该新闻的相关推荐新闻,实现方式就是寻找同类但是ID不同的新闻
    recommend_news = await news.get_recommend_news(new_one.id, db, limit=5)

    return {
        "code": 200,
        "msg": "success",
        "data": {
            "id": new_one.id,
            "title": new_one.title,
            "content": new_one.content,
            "image": new_one.image,
            "author": new_one.author,
            "publishTime": new_one.publish_time,
            "categoryId": new_one.category_id,
            "views": new_one.views,
            "relatedNews": recommend_news
        }
    }