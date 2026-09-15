from pydantic import BaseModel

# 这里创建的是请求体类，而不是表对应的模型类
class UserRequest(BaseModel):

    username: str
    password: str
