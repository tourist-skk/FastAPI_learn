from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from fastapi.responses import FileResponse


app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello World"}
    
# 自定义数据类型
class News(BaseModel):
    id: int
    title: str
    content: str

# 现在设置 id: 1~6，如果不在范围，直接报错
# response_model 约定是一个类型，响应就必须是一个类型
@app.get("/news/{id}")
async def get_news(id: int):
    if id >= 1 and id <= 6:
        return {
            "id": id,
            "title": f"这是第{id}本书",
            "content": f"新华词典"
        }
    else:
        raise HTTPException(status_code=404,detail="您查询的新闻不存在")