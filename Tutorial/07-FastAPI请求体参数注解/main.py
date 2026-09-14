from fastapi import FastAPI
from pydantic import BaseModel,Field


app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello World"}

# 需求: 完成注册功能, 用户名 + 密码 + str
class User(BaseModel):
    # Field(...) 本身不是值，它返回一个 FieldInfo 对象，用来携带「必填、描述、约束」这些额外信息。真正的类型是 str，由 : str 提供。
    username: str = Field(description="用户名",default="LiHua",min_length=2,max_length=10)
    password: str = Field(description="密码")

@app.post("/register")
async def register(user: User):
    return {"message": "User registered"}
        
# 有 : str 和没有的区别

# # 写法 A：有类型
# username: str = Field(..., description="用户名")

# # 写法 B：没类型
# username = Field(..., description="用户名")
# 关键区别：Pydantic 靠类型注解知道数据应该是什么类型。

# 写法 A：Pydantic 知道这是 str，请求体里的 "abc" 会被校验为字符串，123 会被拒绝。
# 写法 B：Field(...) 返回的是 FieldInfo 对象，Pydantic 无法从中推断出「这是字符串」。结果这个字段要么类型变成 Any（不校验），要么报错。
# 简单说：类型注解是 Pydantic 判断字段类型的主要依据，不能省。