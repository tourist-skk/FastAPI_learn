# 由于获取用户信息过于常用，所以需要放到工具函数中
from models.users import User
from crud import users
from config.db_conf import get_db
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


async def get_current_user(
    db: AsyncSession = Depends(get_db, scope="function"),
    authorization: str = Header(..., alias="Authorization"),
) -> User:
    # 当前前端直接传 token；这里也兼容 Bearer token 格式。
    token = authorization.replace("Bearer ", "")
    #token = authorization.split(" ")[1]
    user = await users.get_user_by_token(db, token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token无效")
    return user
