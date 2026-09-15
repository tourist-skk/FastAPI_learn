# 定义模型类

from sqlalchemy import Integer,String,Text, ForeignKey,Index
from sqlalchemy.orm import mapped_column, Mapped
from datetime import datetime
from typing import Optional
from models.Bases import Base



class Category(Base):
    __tablename__ = "news_category"
    id: Mapped[int] = mapped_column(Integer,primary_key=True, autoincrement=True,comment="分类ID")
    name: Mapped[str] = mapped_column(String(50),unique=True,index=True, comment="分类名称",nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer,default=0,comment="排序顺序",nullable=False)
    
    # 类似Java的toString方法
    def __repr__(self):
        return f"<Category(id={self.id}, name={self.name}, sort_order={self.sort_order})>"

class News(Base):
    __tablename__ = "news"
    # 默认只有主键索引,需要手动创建索引,以提升查询效率
    # 创建索引:提升查询效率,根据分类ID查询新闻时,直接从索引中获取,无需遍历所有数据
    # 参数1: 索引名称
    # 参数2: 索引字段名
    __table_args__ = (
        Index("idx_news_category_id", "category_id"),
        Index("idx_publish_time", "publish_time")#按发布时间排序
    )

    id: Mapped[int] = mapped_column(Integer,primary_key=True, autoincrement=True,comment="新闻ID")
    category_id: Mapped[int] = mapped_column(Integer,ForeignKey("news_category.id"),comment="分类ID",nullable=False,)
    title: Mapped[str] = mapped_column(String(255),comment="新闻标题",nullable=False)
    content: Mapped[str] = mapped_column(Text,comment="新闻内容",nullable=False)
    description: Mapped[str | None] = mapped_column(String(500),comment="新闻描述")
    # Optional: 可选字段,数据库中可以为空
    # Optional[str]        # from typing import Optional
    # == str | None        # Python 3.10+ 推荐写法
    # == Union[str, None]  # 旧式显式写法
    image: Mapped[Optional[str]] = mapped_column(String(255),comment="新闻图片URL")
    author: Mapped[Optional[str]] = mapped_column(String(50),comment="新闻作者")
    views: Mapped[int] = mapped_column(Integer,default=0,comment="新闻点击量",nullable=False)
    publish_time: Mapped[Optional[datetime]] = mapped_column(comment="发布时间")
    
    # 类似Java的toString方法
    def __repr__(self):
        return f"<News(id={self.id}, title={self.title}, views={self.views}, publish_time={self.publish_time})>"


