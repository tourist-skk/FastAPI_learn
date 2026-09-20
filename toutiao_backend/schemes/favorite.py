from pydantic import BaseModel, Field, ConfigDict

class FavoriteCheckResponse(BaseModel):
    is_favorite: bool = Field(..., description="是否收藏", serialization_alias="isFavorite")
    
# 请求体参数
class FavoriteAddRequest(BaseModel):
    news_id: int = Field(..., description="新闻ID", validation_alias="newsId")
    