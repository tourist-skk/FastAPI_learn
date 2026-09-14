from fastapi import APIRouter

# 创建APIRouter实例
# prefix: /api/news 路由前缀(API 接口规范标签)
# tags: news 路由标签(API 接口规范标签)
router = APIRouter(prefix="/api/news", tags=["news"])

@router.get("/category")
def get_category_news():
    return {"message": "获取新闻分类新闻"}
