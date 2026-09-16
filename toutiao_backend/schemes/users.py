from pydantic import BaseModel,Field,ConfigDict
from typing import Optional

# 核心目的: 验证返回数据的格式是否符合预期

class UserRequest(BaseModel):
    username: str
    password: str

class UserInfoBase(BaseModel):
    nickname: Optional[str] = Field(None,max_length=50,description="用户昵称")
    bio: Optional[str] = Field(None,max_length=500,description="用户简介")
    avatar: Optional[str] = Field(None,max_length=255,description="用户头像")
    gender: Optional[str] = Field(None,max_length=10,description="用户性别")

# 可选类 + 必须的属性
class UserInfoResponse(UserInfoBase):
    id: int
    username: str
    model_config = ConfigDict(
        from_attributes=True
    )


# 响应data的数据类型
class UserAuthResponse(BaseModel):
    token: str
    user_Info: UserInfoResponse = Field(alias="userInfo",description="用户信息")

    # 模型类配置
    model_config = ConfigDict(
        populate_by_name=True, # 允许通过字段名而不是字段索引来设置值
        from_attributes=True # 从数据库模型中获取值，而不是从请求体中获取值
    )
    
