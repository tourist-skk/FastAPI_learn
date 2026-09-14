from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field
from fastapi.responses import FileResponse


app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello World"}
# http表示处理http请求
@app.middleware("http")
async def middleware1(request,call_next):
    print("中间件1 开始处理-------")
    response = await call_next(request)
    print("中间件1 完成处理-------")
    return response

@app.middleware("http")
async def middleware2(request,call_next):
    print("中间件2 开始处理-------")
    response = await call_next(request)
    print("中间件2 完成处理-------")
    return response

# 中间件的运行顺序是自底向上，栈的实现