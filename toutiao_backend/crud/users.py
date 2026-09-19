from models.users import User, UserToken
from schemes.users import UserRequest,UserUpdateRequest,UserUpdatePasswordRequest
from datetime import datetime
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,update
from typing import Optional
from fastapi import HTTPException,status
from utils.security import hash_password,verify_password
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

async def authenticate_user(db: AsyncSession, user_request: UserRequest) -> User:
    existing_user = await get_user_by_username(db, user_request.username)
    if not existing_user:
        return None
    is_valid = verify_password(user_request.password, existing_user.password)
    if not is_valid:
        return None
    return existing_user

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

# 根据token查询用户 -> 验证token是否有效 -> 返回用户信息
async def get_user_by_token(db: AsyncSession, token: str) -> Optional[User]:
    stmt = select(UserToken).where(UserToken.token == token)
    result = await db.execute(stmt)
    db_token = result.scalar_one_or_none()
    # 1. 验证token是否存在
    # 2. 验证token是否过期
    if not db_token or db_token.expires_at < datetime.now():
        return None
    stmt = select(User).where(User.id == db_token.user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def update_user_info(db: AsyncSession, username: str, user_update_request: UserUpdateRequest) -> None:
    # 1. 更新用户信息
    # model_dump: 将pydantic模型实例转换为字典
    # **: 展开字典，将键值对作为参数传递给 values 方法
    # 没有设置值的不更新
    stmt = update(User).where(User.username == username).values(**user_update_request.model_dump(exclude_unset=True,exclude_none=True))
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    # 2. 提交事务
    # await db.commit()
    # 也可以直接输入 user，然后在这里db.refresh(user)
    user = await get_user_by_username(db, username)
    
    # 3. 查询更新后的用户信息
    await db.refresh(user)
    
    return user

async def update_user_password(db: AsyncSession, username: str, user_update_password_request: UserUpdatePasswordRequest) -> None:
    # 1. 验证旧密码是否正确
    user = await get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    is_valid = verify_password(user_update_password_request.old_password, user.password)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="旧密码错误")
    if user_update_password_request.new_password == user_update_password_request.old_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码不能与旧密码相同")
    # 2. 更新新密码 : 将新密码加密后更新到数据库中
    user_new_password = hash_password(user_update_password_request.new_password)
    update_stmt = update(User).where(User.username == username).values(password=user_new_password)
    await db.execute(update_stmt)
    # 确保SQLAlchemy 接管该对象，避免会话过期导致不能提交事务
    #await db.commit()
    # 4. 查询更新后的用户信息
    await db.refresh(user)
    return user

# # 修改密码：验证旧密码 -> 新密码加密 -> 修改密码
# async def change_password(
#     db: AsyncSession,
#     user: User,
#     old_password: str,
#     new_password: str
# ):
#     if not security.verify_password(old_password, user.password):
#         return False
 
#     hashed_new_pwd = security.get_hash_password(new_password)
#     user.password = hashed_new_pwd
 
#     # 更新：由 SQLAlchemy 真正接管这个 User 对象，确保可以 commit
#     # 规避 session 过期或关闭导致的不能提交的问题
#     db.add(user)
#     await db.commit()
#     await db.refresh(user)
#     return True