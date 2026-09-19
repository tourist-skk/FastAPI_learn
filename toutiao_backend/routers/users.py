from fastapi import APIRouter
from utils.response import success_response
from schemes.users import UserRequest,UserAuthResponse,UserInfoResponse,UserUpdatePasswordRequest
from crud import users
from config.db_conf import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends,HTTPException,status
from schemes.users import UserUpdateRequest
from utils.auth import get_current_user
from models.users import User

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
    # 登陆逻辑:
    # 1. 检查用户名是否存在
    # 2. 匹配用户名和密码
    # 3. 生成访问令牌
    # 4. 响应结果

    existing_user = await users.authenticate_user(db, user_request)
    # 具体的业务错误还是需要写if判断
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    # 2. 匹配用户名和密码
    user_token = await users.create_user_token(db, existing_user.id)
    # model_validate 会从输入参数中提取 调用类的属性
    return success_response(message="登录成功",data=UserAuthResponse(token=user_token.token,user_Info=UserInfoResponse.model_validate(existing_user)))


@router.get("/info")
async def get_user_info(user: User = Depends(get_current_user)):
    # 有token没有过期，才能获取用户信息
    # 前端通过 Authorization 传递 token，由认证依赖验证后注入当前用户。
    # 需要放到中间件吗?
    # 这里不需要返回token字段
    user_info = UserInfoResponse.model_validate(user)
    return success_response(message="获取用户信息成功",data=user_info)

# 为什么这里的参数没有db
# 方法思路: 进入请求 -> 检查token有效性 -> 从token中获取用户信息 -> 更新用户信息 -> 返回成功
@router.put("/update")
async def update_user_info(user_update_request: UserUpdateRequest,user: User = Depends(get_current_user),db: AsyncSession = Depends(get_db, scope="function")):
    # 1. 更新用户信息
    user = await users.update_user_info(db, user.username, user_update_request)
    # 2. 响应结果
    user_info = UserInfoResponse.model_validate(user)
    return success_response(message="更新用户信息成功",data=user_info)

@router.put("/password")
async def change_password(user_update_password_request: UserUpdatePasswordRequest,user: User = Depends(get_current_user),db: AsyncSession = Depends(get_db, scope="function")):
    # 1. 更新用户密码
    await users.update_user_password(db, user.username, user_update_password_request)
    # 2. 响应结果
    return success_response(message="更新用户密码成功")
