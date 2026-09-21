from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from schemes.news import NewsBase



class FavoriteCheckResponse(BaseModel):
    is_favorite: bool = Field(..., description="是否收藏", serialization_alias="isFavorite")
    
# 请求体参数
class FavoriteAddRequest(BaseModel):
    news_id: int = Field(..., description="新闻ID", validation_alias="newsId")

    # "list": [
    #   {
    #     "id": 1,
    #     "title": "新闻标题",
    #     "description": "",
    #     "image": "",
    #     "author": "",
    #     "publishTime": "2023-01-01T00:00:00",
    #     "categoryId": 1,
    #     "views": 1,
    #     "favoriteTime": "2023-01-01T00:00:00"
    #   }
# 继承新闻的表类，添加收藏时间字段
class NewsItemBase(NewsBase):
    # id: int = Field(..., description="新闻ID")
    # title: str = Field(..., description="新闻标题")
    # description: str | None = Field(None, description="新闻描述")
    # image: str | None = Field(None, description="新闻图片URL")
    # author: str | None = Field(None, description="新闻作者")
    # publish_time: datetime = Field(..., description="发布时间", serialization_alias="publishTime")
    # category_id: int = Field(..., description="分类ID", serialization_alias="categoryId")
    # views: int = Field(..., description="新闻点击量")
    created_at: datetime = Field(..., description="收藏时间", serialization_alias="favoriteTime")
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class FavoriteListResponse(BaseModel):
    total: int = Field(..., description="收藏总数")
    has_more: bool = Field(..., description="是否有更多数据", serialization_alias="hasMore")
    news_items: list[NewsItemBase] = Field(..., description="收藏列表", alias="list")
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
