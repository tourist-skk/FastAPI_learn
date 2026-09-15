from fastapi import APIRouter,Query,Path
from crud import users
from config.db_conf import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends,HTTPException
from models.users import UserRequest

router = APIRouter(prefix="/api/users",tags=["users"])

@router.post("/register")
def register(
    user_request: UserRequest,
    db: AsyncSession = Depends(get_db)
    ):


    return {
        "code": 200,
        "message": "注册成功",
        "data": {
            "token": "用户访问令牌",
            "userInfo": {
                "id": 1,
                "username": "users.username",
                "bio": "这个人很懒，什么都没留下",
                "avatar": "https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg"
            }
        }
    }
        