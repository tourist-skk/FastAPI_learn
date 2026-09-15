from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class ModelBase(DeclarativeBase):
    """所有模型共享的声明式基类，不自动添加字段。"""


class Base(ModelBase):
    __abstract__ = True

    # ORM模型类需要与数据库字段保持一致
    # mapped_column 参数说明：
    # DateTime：这一列的数据库类型是日期时间（对应 DB 里的 DATETIME/TIMESTAMP）
    # default：插入新行时，若没给这个字段，就自动填当前时间
    # onupdate：更新该行时，若没显式指定这个字段，就自动刷新为当前时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        comment="创建时间"
    )
    # Mapped[datetime]：Mapped[datetime] 是类型注解，声明"这一列在 Python 内存里对应的是 datetime 对象"（读出来/写进去时用 datetime 类型）。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间"
    )
