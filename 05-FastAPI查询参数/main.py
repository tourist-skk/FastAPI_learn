from fastapi import FastAPI, Query, Path


app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello World"}

# 需求：查询新闻 -> 分页, skip: 跳过的记录数 , limit: 返回的记录数
@app.get("/news/news_list")
async def get_news_list(
    skip: int = Query(0,description="跳过的记录数",lt=1000,gt=0), 
    limit: int = Query(10,description="返回的记录数",lt=100,gt=0)
    ):
    return {"skip": skip, "limit": limit}

# 路径参数可以使用Path进行额外注解。
# 查询参数也可以，但不是Path，而是Query