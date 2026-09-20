from sqlalchemy import Column, Integer, ForeignKey, DateTime
from datetime import datetime
from models.Bases import ModelBase
from models.users import User
from models.news import News
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped

class Favorite(ModelBase):
    __tablename__ = "favorite"

    __table_args__ = (
        # 唯一约束, 当前用户对当前新闻只能收藏一次
        # 保证表中的某几列组合起来不能出现重复值。
        UniqueConstraint("user_id", "news_id", name="unique_favorite"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = Column(Integer, ForeignKey(User.id), index=True, nullable=False)
    news_id: Mapped[int] = Column(Integer, ForeignKey(News.id), index=True, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.now, comment="创建时间", nullable=False)
    def __repr__(self):
        return f"Favorite(id={self.id}, user_id={self.user_id}, news_id={self.news_id}, created_at={self.created_at})"

    