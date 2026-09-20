# 负责挂载路由
from fastapi import FastAPI
from routers import news,users,favorite
from fastapi.middleware.cors import CORSMiddleware
from utils.exception_handlers import register_exception_handlers
# 创建FastAPI实例
app = FastAPI()
# 挂载新闻路由
app.include_router(news.router)
# 挂载用户路由
app.include_router(users.router)
# 挂载收藏路由
app.include_router(favorite.router)
# 注册异常处理函数
register_exception_handlers(app)

@app.get("/")
def read_root():
    return {"message": "Hello World"}

# 解决前后端跨域问题
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许 * 来源的请求
    allow_credentials=True, # 允许携带凭证（如 Cookie、Authorization 等）
    allow_methods=["*"], # 允许所有 请求 方法
    allow_headers=["*"], # 允许所有 请求 头
   )
