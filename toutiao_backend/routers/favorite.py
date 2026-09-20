# 创建APIRouter实例
# prefix: /api/news 路由前缀(API 接口规范标签)
# tags: news 路由标签(API 接口规范标签)
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query
from utils.auth import get_current_user
from utils.response import success_response
from config.db_conf import get_db
from models.users import User
from crud.favorite import is_news_favorite
from schemes.favorite import FavoriteCheckResponse



router = APIRouter(prefix="/api/favorite", tags=["favorite"])

@router.get("/check")
async def check_favorite(
        db: AsyncSession = Depends(get_db), 
        user: User = Depends(get_current_user), 
        news_id: int = Query(..., alias="newsId", description="新闻ID")
    ) :
    """
    返回示例:
    data: {
        "isFavorite": true
    }
    返回的data必须是 字典
    """
    is_favorite = await is_news_favorite(user.id, news_id, db)

    return success_response(message="检查收藏成功",data=FavoriteCheckResponse(is_favorite=is_favorite))
    # 是否等同于 return success_response(message="检查收藏成功",data={"is_favorite": is_favorite})
