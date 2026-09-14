# 负责挂载路由
from fastapi import FastAPI
from routers import news

# 创建FastAPI实例
app = FastAPI()
# 挂载新闻路由
app.include_router(news.router)

@app.get("/")
def read_root():
    return {"message": "Hello World"}