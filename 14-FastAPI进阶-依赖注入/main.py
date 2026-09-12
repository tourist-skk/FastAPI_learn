from fastapi import FastAPI,HTTPException,Depends,Query



app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello World"}


# 分页参数逻辑共用: 新闻列表和用户列表
# 1. 依赖项
# 2. 导入Depends
async def common_parameters(
        skip:int = Query(default=0,ge=0)
        ,limit:int = Query(default=10,le=60)
        ):
    return {"skip":skip,"limit":limit}

# 3. 声明依赖项
@app.get("/news/news_list")
async def get_news_list(commons=Depends(common_parameters)):
    return {"message":"hello","result":commons}

@app.get("/user/user_list")
async def get_user_list():
    return {"message":"hello"}