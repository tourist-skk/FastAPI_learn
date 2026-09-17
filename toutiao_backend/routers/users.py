from fastapi import APIRouter
from utils.response import success_response
from schemes.users import UserRequest,UserAuthResponse,UserInfoResponse
from crud import users
from config.db_conf import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends,HTTPException,status
from schemes.users import UserRequest

router = APIRouter(prefix="/api/user",tags=["users"])

@router.post("/register")
async def register(
    user_request: UserRequest,
    # 对于含有 yield 的依赖，FastAPI 默认在响应发送之后执行退出代码。本项目支持 Depends(get_db, scope="function")，使退出代码在路由函数结束后、响应发送之前执行。
    # 因为 get_db 的退出代码包含 commit()，这样才能先确认提交成功，再发送成功响应。
    db: AsyncSession = Depends(get_db, scope="function")
    ):
    # 1. 检查用户名是否存在
    existing_user = await users.get_user_by_username(db, user_request.username)
    # if existing_user:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

    # 2. 创建用户
    # 2.1 计算密码哈希
    # 2.2 创建用户后，需要生成访问令牌
    new_user = await users.create_user(db, user_request)
    # 2.3 生成访问令牌
    user_token = await users.create_user_token(db, new_user.id)
    # 3. 响应结果
    # return {
    #     "code": 200,
    #     "message": "注册成功",
    #     "data": {
    #         "token": user_token.token,
    #         "userInfo": {
    #             "id": new_user.id,
    #             "username": new_user.username,
    #             "bio": new_user.bio,
    #             "avatar": new_user.avatar
    #         }
    #     }
    # }
    # 将ORM对象转为pydantic类型
    return success_response(message="注册成功",data=UserAuthResponse(token=user_token.token,user_Info=UserInfoResponse.model_validate(new_user)))

# 登录
@router.post("/login")
async def login(
    user_request: UserRequest,
    db: AsyncSession = Depends(get_db, scope="function")
    ):
    # 1. 检查用户名是否存在
    existing_user = await users.get_user_by_username(db, user_request.username)
    # 2. 匹配用户名和密码
    is_valid = await users.verify_password(user_request.password, existing_user.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码错误")
    user_token = await users.create_user_token(db, existing_user.id)

    return success_response(message="登录成功",data=UserAuthResponse(token=user_token.token,user_Info=UserInfoResponse.model_validate(existing_user)))