from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class NewsBase(BaseModel):
    id: int = Field(..., description="新闻ID")
    title: str = Field(..., description="新闻标题")
    description: str | None = Field(None, description="新闻描述")
    image: str | None = Field(None, description="新闻图片URL")
    author: str | None = Field(None, description="新闻作者")
    publish_time: datetime = Field(..., description="发布时间", serialization_alias="publishTime")
    category_id: int = Field(..., description="分类ID", serialization_alias="categoryId")
    views: int = Field(..., description="新闻点击量")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )