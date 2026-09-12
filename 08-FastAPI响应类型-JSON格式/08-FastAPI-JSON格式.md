# 08 · FastAPI 响应类型：JSON 格式

JSON 是 Web API 最常见的响应格式。FastAPI 默认会把路径操作函数返回的 Python 对象 经由jsonable_encoder转换成 JSON兼容格式，并包装为JSONResponse对象返回，并设置响应头：

```http
Content-Type: application/json
```

## 常见响应类型速览

这些响应类可以从 `fastapi.responses` 导入。本表只做快速对比，后续小节再分别学习具体格式。[FastAPI 可用响应类型](https://fastapi.tiangolo.com/advanced/custom-response/#available-responses)

| 响应类型 | 用途 | 示例 |
| --- | --- | --- |
| `JSONResponse` | 返回 JSON 数据 | `JSONResponse(content={"status": "ok"})` |
| `HTMLResponse` | 返回 HTML 页面内容 | `HTMLResponse(content="<h1>Hello</h1>")` |
| `PlainTextResponse` | 返回不带 HTML 格式的纯文本 | `PlainTextResponse(content="Hello")` |
| `RedirectResponse` | 将客户端重定向到另一个地址 | `RedirectResponse(url="/docs")` |
| `FileResponse` | 返回磁盘中的文件 | `FileResponse(path="report.pdf")` |
| `StreamingResponse` | 分批返回较大内容或连续数据 | `StreamingResponse(iter_data(), media_type="text/plain")` |

## 1. 直接返回字典或列表

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/user")
def get_user():
    return {"id": 1, "name": "Alice", "active": True}


@app.get("/numbers")
def get_numbers():
    return [1, 2, 3]
```

FastAPI 会将字典转换成 JSON 对象，将列表转换成 JSON 数组。

```json
{
  "id": 1,
  "name": "Alice",
  "active": true
}
```

注意 Python 的 `True`、`False`、`None` 在 JSON 中分别是 `true`、`false`、`null`。

## 2. 返回 Pydantic 模型

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float


@app.get("/item", response_model=Item)
def get_item():
    return {"name": "notebook", "price": 12.5}
```

`response_model=Item` 声明响应应符合 `Item` 模型。FastAPI 会校验、序列化返回值，并将响应结构写入 `/docs`。[响应模型](https://fastapi.tiangolo.com/tutorial/response-model/)

函数也可以直接返回一个 `Item` 对象：

```python
@app.get("/item-object", response_model=Item)
def get_item_object():
    return Item(name="notebook", price=12.5)
```

## 3. 显式返回 `JSONResponse`

需要直接控制状态码、响应头或 JSON 内容时，可以使用 `JSONResponse`：

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()


@app.post("/items")
def create_item():
    return JSONResponse(
        status_code=201,
        content={"message": "创建成功"},
        headers={"X-Result": "created"},
    )
```

直接返回 `JSONResponse` 时，FastAPI 会把它原样发送，不再自动使用 Pydantic 转换其内容。因此 `content` 应当已经是 JSON 兼容的数据。[直接返回响应](https://fastapi.tiangolo.com/advanced/response-directly/)

一般接口直接返回字典、列表或 Pydantic 模型即可；需要精确控制响应时再使用 `JSONResponse`。

## 4. 不要手动返回 JSON 字符串

```python
# 不推荐
return '{"message": "ok"}'
```

上面的返回值是一个普通字符串，FastAPI 会把它编码成 JSON 字符串，而不是 JSON 对象。推荐直接返回：

```python
return {"message": "ok"}
```

## 5. 使用 `.http` 文件测试

```http
### 获取用户 JSON
GET http://127.0.0.1:8000/user
Accept: application/json

### 获取商品 JSON
GET http://127.0.0.1:8000/item
Accept: application/json
```

运行请求后，可以观察响应体以及 `Content-Type: application/json` 响应头。

本节需要记住：**普通 Python 数据由 FastAPI 自动转换为 JSON；`response_model` 用于约束响应结构；`JSONResponse` 用于直接控制 JSON 响应。**
