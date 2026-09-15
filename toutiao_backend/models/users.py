from sqlalchemy import ForeignKey
from pydantic import BaseModel
from models.Bases import Base, ModelBase
from datetime import datetime
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy import Index,Integer,String,DateTime,Enum
# 这里创建的是请求体类，而不是表对应的模型类
from typing import Optional
class UserRequest(BaseModel):

    username: str
    password: str

# 用户表
# cid  name        type          notnull  dflt_value         pk
# ---  ----------  ------------  -------  -----------------  --
# 0    id          INTEGER       0                           1
# 1    username    VARCHAR(50)   1                           0
# 2    password    VARCHAR(255)  1                           0
# 3    nickname    VARCHAR(50)   0        NULL               0
# 4    avatar      VARCHAR(255)  0        NULL               0
# 5    gender      TEXT          0        'unknown'          0
# 6    bio         VARCHAR(500)  0        NULL               0
# 7    phone       VARCHAR(20)   0        NULL               0
# 8    created_at  DATETIME      1        CURRENT_TIMESTAMP  0
# 9    updated_at  DATETIME      1        CURRENT_TIMESTAMP  0
class User(Base):
    __tablename__ = "user"
    __table_args__ = (
        Index('username_UNIQUE', "username"),
        Index('phone_UNIQUE', "phone")
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,comment="用户id")
    username: Mapped[str] = mapped_column(String(50),unique=True,comment="用户名",nullable=False)
    password: Mapped[str] = mapped_column(String(255),comment="密码",nullable=False)
    nickname: Mapped[Optional[str]] = mapped_column(String(50),comment="昵称")
    bio: Mapped[str | None] = mapped_column(comment="个人简介", default='这个人很懒，什么都没留下')
    avatar: Mapped[Optional[str]] = mapped_column(String(255),comment="头像")
    gender: Mapped[str | None] = mapped_column(Enum("male", "female", "unknown"),default="unknown",comment="性别")
    phone: Mapped[Optional[str]] = mapped_column(String(20),comment="手机号",unique=True)


# cid  name        type          notnull  dflt_value         pk
# ---  ----------  ------------  -------  -----------------  --
# 0    id          INTEGER       0                           1
# 1    user_id     INTEGER       1                           0
# 2    token       VARCHAR(255)  1                           0
# 3    expires_at  DATETIME      1                           0
# 4    created_at  DATETIME      1        CURRENT_TIMESTAMP  0
class UserToken(ModelBase):
    __tablename__ = "user_token"
    __table_args__ = (
        Index('token_UNIQUE', "token"),
        Index('fk_user_token_user_id', "user_id")
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,comment="用户token id")
    user_id: Mapped[int] = mapped_column(Integer,ForeignKey(User.id),nullable=False,comment="用户id")
    token: Mapped[str] = mapped_column(String(255),unique=True,nullable=False,comment="令牌值")
    expires_at: Mapped[datetime] = mapped_column(DateTime,nullable=False,comment="过期时间")
    created_at: Mapped[datetime] = mapped_column(DateTime,default=datetime.now,nullable=False,comment="创建时间")

    def __repr__(self):
        return f"UserToken(id={self.id}, user_id={self.user_id}, token={self.token}, expires_at={self.expires_at}, created_at={self.created_at})"
# DeclarativeBase 在 SQLAlchemy 2.0 里是一个特殊的"模板/工厂"类，它不允许被直接当作模型类的父类使用。
# SQLAlchemy 在 DeclarativeBase.__init_subclass__ 里显式做了检查，一旦发现某个类直接继承 DeclarativeBase，就抛 InvalidRequestError。
