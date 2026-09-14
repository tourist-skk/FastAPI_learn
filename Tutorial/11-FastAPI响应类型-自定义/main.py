from fastapi import FastAPI
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


# response_model 约定是一个类型，响应就必须是一个类型
@app.get("/news/{id}",response_model=News)
async def get_news(id: int):
    file_path = "./files/pencil.jpg"
    return {
        "id": id,
        "title": f"这是第{id}本书",
        "content": f"新华词典"
    }