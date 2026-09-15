from fastapi import APIRouter,Query,Path
from crud import users
from config.db_conf import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends,HTTPException,status
from models.users import UserRequest

router = APIRouter(prefix="/api/user",tags=["users"])

@router.post("/register")
async def register(
    user_request: UserRequest,
    # 在发送响应前执行 get_db 的提交；异常时回滚用户和令牌。
    db: AsyncSession = Depends(get_db, scope="function")
    ):
    # 1. 检查用户名是否存在
    existing_user = await users.get_user_by_username(db, user_request.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    # 2. 创建用户
    # 2.1 计算密码哈希
    # 2.2 创建用户后，需要生成访问令牌
    new_user = await users.create_user(db, user_request)
    # 2.3 生成访问令牌
    user_token = await users.create_user_token(db, new_user.id)
    # 3. 响应结果
    return {
        "code": 200,
        "message": "注册成功",
        "data": {
            "token": user_token.token,
            "userInfo": {
                "id": new_user.id,
                "username": new_user.username,
                "bio": new_user.bio,
                "avatar": new_user.avatar
            }
        }
    }
