from fastapi import APIRouter
from crud import news
from config.db_conf import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from models.news import Category

# 创建APIRouter实例
# prefix: /api/news 路由前缀(API 接口规范标签)
# tags: news 路由标签(API 接口规范标签)
router = APIRouter(prefix="/api/news", tags=["news"])

# 
@router.get("/category")
async def get_category_news(skip:int=0, limit:int=100, db: AsyncSession = Depends(get_db)):
    # 实际这里需要返回分页数据，因此需要查询数据库
    category_list = await news.get_category_list(skip, limit, db)
    return {
        "code": 200,
        "msg": "success",
        "data": category_list
    }
