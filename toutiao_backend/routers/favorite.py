# 创建APIRouter实例
# prefix: /api/news 路由前缀(API 接口规范标签)
# tags: news 路由标签(API 接口规范标签)
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query, HTTPException, status
from utils.auth import get_current_user
from utils.response import success_response
from config.db_conf import get_db
from models.users import User
from crud import favorite
from schemes.favorite import FavoriteCheckResponse, FavoriteAddRequest, FavoriteListResponse



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
    is_favorite = await favorite.is_news_favorite(user.id, news_id, db)

    return success_response(message="检查收藏成功",data=FavoriteCheckResponse(is_favorite=is_favorite))
    # 是否等同于 return success_response(message="检查收藏成功",data={"is_favorite": is_favorite})

# 前端输入的参数需要进入 request 中,需要与 request 中的字段名一致
@router.post("/add")
async def add_favorite(
        request: FavoriteAddRequest,
        db: AsyncSession = Depends(get_db, scope="function"),
        user: User = Depends(get_current_user),
    ) :
    """
    添加当前用户对指定新闻的收藏，重复添加时返回已有记录。
    """
    result = await favorite.add_favorite(request.news_id, user.id, db)

    return success_response(message="收藏成功",data=result)

@router.delete("/remove")
async def remove_favorite(
        news_id: int = Query(..., alias="newsId", description="新闻ID"),
        db: AsyncSession = Depends(get_db, scope="function"),
        user: User = Depends(get_current_user),
    ) :
    """
    移除当前用户对指定新闻的收藏，移除时返回已有记录。
    """
    result = await favorite.remove_favorite(news_id, user.id, db)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="收藏记录不存在")
    
    return success_response(message="移除收藏成功")


@router.get("/list")
async def get_favorite_list(
        page: int = Query(1,ge=1, alias="page", description="页码"),
        page_size: int = Query(10,ge=1,le=100, alias="pageSize", description="每页数量"),
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user)
    ) :
    """
    返回当前用户收藏的新闻列表
      "data": {
    "list": [
      {
        "id": 1,
        "title": "新闻标题",
        "description": "",
        "image": "",
        "author": "",
        "publishTime": "2023-01-01T00:00:00",
        "categoryId": 1,
        "views": 1,
        "favoriteTime": "2023-01-01T00:00:00"
      }
    ],
    "total": 1,
    "hasMore": false
  }
    """
    result = await favorite.get_favorite_list(user.id, page, page_size, db)
    total = await favorite.get_favorite_count(user.id, db)
    has_more = (page - 1) * page_size + len(result) < total
    return success_response(
        message="收藏列表成功",
        data=FavoriteListResponse(total=total, has_more=has_more, list=result),
    )

@router.delete("/clear")
async def clear_favorite(
        db: AsyncSession = Depends(get_db, scope="function"),
        user: User = Depends(get_current_user),
    ) :
    """
    清空当前用户的所有收藏记录
    """
    is_delete,count = await favorite.clear_favorite(user.id, db)
    if not is_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="收藏记录不存在")
    return success_response(message=f"清空{count}条收藏")
        