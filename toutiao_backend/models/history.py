from pydantic import Field
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from models.Bases import ModelBase
from models.users import User
from models.news import News
from datetime import datetime
from sqlalchemy.orm import Mapped


# 数据库表中不存在created_at字段、updated_at字段
# 浏览时间在表中已经存在了
class History(ModelBase):
    __tablename__ = "history"
    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = Column(Integer, ForeignKey(User.id), index=True, nullable=False)
    news_id: Mapped[int] = Column(Integer, ForeignKey(News.id), index=True, nullable=False)
    view_time: Mapped[datetime] = Column(DateTime, default=datetime.now, comment="浏览时间", nullable=False)

    def __repr__(self):
        return f"History(id={self.id}, user_id={self.user_id}, news_id={self.news_id}, view_time={self.view_time})"
