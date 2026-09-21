from pydantic import BaseModel,Field,ConfigDict
from schemes.news import NewsBase
from datetime import datetime




class HistoryAddRequest(BaseModel):
    news_id: int = Field(..., gt=0,description="新闻ID", alias="newsId")


class HistoryItem(NewsBase):
    id: int = Field(..., description="浏览记录ID")
    view_time: datetime = Field(..., description="浏览时间", alias="viewTime")
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class HistoryListResponse(BaseModel):
    history_list: list[HistoryItem] = Field(..., description="浏览记录列表",alias="list")
    total: int = Field(..., description="总记录数")
    hasMore: bool = Field(..., description="是否有更多记录",alias="hasMore")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
    
