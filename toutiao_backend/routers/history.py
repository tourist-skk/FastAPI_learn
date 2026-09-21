from fastapi import APIRouter, Depends, Query
from config.db_conf import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from models.users import User
from utils.response import success_response
from utils.auth import get_current_user
from schemes.history import HistoryAddRequest, HistoryListResponse
from crud import history




router = APIRouter(prefix="/api/history", tags=["history"])

@router.post("/add")
async def add_one_history(
        request: HistoryAddRequest,
        user : User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
    # 添加浏览记录
    result = await history.add_history(user.id, request.news_id, db)

    return success_response(message="添加成功", data=result)


@router.get("/list")
async def get_history_list(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(10, ge=1, le=100, description="每页数量"),
        user : User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
    """
    {
  "code": 200,
  "message": "success",
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
        "viewTime": "2023-01-01T00:00:00"
      }
    ],
    "total": 1,
    "hasMore": false
  }
}
    """
    # 获取用户浏览记录
    result = await history.get_history_list( user.id, page, page_size, db)
    # 获取用户浏览记录数量
    count = await history.get_count_history(user.id, db)
    hasMore = (page - 1) * page_size + len(result) < count
    return success_response(message="获取成功列表", data=HistoryListResponse(history_list=result, total=count, hasMore=hasMore))

@router.delete("/delete/{news_id}")
async def delete_history(
        news_id: int,
        user : User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
    # 删除浏览记录
    result = await history.delete_history(news_id, user.id, db)
    return success_response(message="删除成功")

@router.delete("/clear")
async def clear_history(
        user : User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
    # 清空用户浏览记录
    result = await history.clear_history(user.id, db)
    return success_response(message=f"清空浏览记录成功，删除了{result}条记录")
