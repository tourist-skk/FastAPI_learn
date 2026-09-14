from fastapi import FastAPI, Path

# 常见FastAPI实例
app = FastAPI(title="FastAPI 入门练习")

# 定义接口，返回首页
# 访问 http://localhost:8000/ 即可查看 message
# 如果在下面函数定义将 def 前加上 async，则会被定义为异步函数
@app.get("/")#| 把 `GET /` 请求关联到紧接着定义的函数 |
def read_home():# 定义接收请求后执行的处理逻辑
    return {"message": "我的第一个 FastAPI 接口运行成功！666"}

# 1. 路径参数
@app.get("/hello/{name}")#从路径读取名字，作为字符串传给函数
def say_hello(name: str=Path(..., max_length=10,description="要打招呼的人")):# name: str 参数类型注解，约定参数的数据类型
    return {"message": f"你好，{name}！"}
# Path(...) 为路径参数添加限制注解
# 第一个... 表示必填 。Thought
#... 是 Python 的一个内置对象，叫 Ellipsis（省略号）。在 Path(...) 里，它作为第一个参数表示：这个参数是必填的，没有默认值。
# 第二个开始填入参数

# 创建后，使用 uv run dev main.py 启动 FastAPI 服务
# 访问 http://localhost:8000/ 即可查看 message
# 访问 http://localhost:8000/hello/FastAPI 即可查看 "你好，FastAPI！"
# 访问 http://localhost:8000/hello/World 即可查看 "你好，World！"

# 参数定义
# 1. 路径参数
async def test():
    pass