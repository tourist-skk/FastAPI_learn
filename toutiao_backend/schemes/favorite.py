from pydantic import BaseModel, Field

class FavoriteCheckResponse(BaseModel):
    is_favorite: bool = Field(..., description="是否收藏", serialization_alias="isFavorite")
    
