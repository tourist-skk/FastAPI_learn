from models.users import User, UserToken
from schemes.users import UserRequest
from datetime import datetime
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from utils.security import hash_password
import uuid



# 根据用户名查询数据库
async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    return result.scalars().first()

async def create_user(db: AsyncSession, user_request: UserRequest) -> User:
    # 1. 安装 密码加密 passllib: uv add "passlib[bcrypt]"
    # 2. 加密密码
    encrypted_password = hash_password(user_request.password)

    user = User(username=user_request.username, password=encrypted_password)
    db.add(user)
    # 执行 INSERT 并取得用户 ID，事务由 get_db 统一提交。
    await db.flush()
    # 读取数据库中的默认值，但不提前提交事务。
    await db.refresh(user)
    return user

async def create_user_token(db: AsyncSession, user_id: int) -> UserToken:
    # 1. 生成token，如果当前用户存在token，就更新旧的token
    token = str(uuid.uuid4())
    expires_at = datetime.now() + timedelta(days=7)
    # 2. 如果当前用户不存在token，就创建新的token
    # 3. 返回新的token
    stmt = select(UserToken).where(UserToken.user_id == user_id)
    result = await db.execute(stmt)
    # first() 会关闭结果，只提取一次并复用对象。
    user_token = result.scalars().first()
    if user_token:
        # 更新旧token
        user_token.token = token
        user_token.expires_at = expires_at
    else:
        user_token = UserToken(user_id=user_id, token=token, expires_at=expires_at)
    db.add(user_token)
    # 令牌与用户留在同一事务，任一步失败都可以一起回滚。
    await db.flush()
    # 读取数据库中的默认值，但不提前提交事务。
    await db.refresh(user_token)
    return user_token
