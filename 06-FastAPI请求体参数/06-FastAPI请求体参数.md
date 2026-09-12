# 06 · FastAPI 请求体参数

请求体（Request Body）是客户端发送给服务端的一段内容，常用于提交 JSON 数据。

## 1. 请求体在 HTTP 请求中的位置

一个简化的 HTTP 请求如下：

```http
POST /items HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json

{
  "name": "notebook",
  "price": 12.5
}
```

它由三部分组成：

1. 请求行：`POST /items HTTP/1.1` 方法、URL、HTTP版本号
2. 请求头：例如 `Content-Type: application/json`
3. 请求体：空行后面的 JSON 数据

`Content-Type` 告诉服务端如何解释请求体。本例使用 `application/json`。

## 2. 请求体的作用

路径和查询参数适合传递编号、筛选条件等较短的数据；请求体适合传递一个结构化对象，例如商品、用户资料或订单。

常见 HTTP 方法：

| 方法 | 请求体的常见用途 |
| --- | --- |
| `POST` | 创建资源或提交数据 |
| `PUT` | 整体替换资源 |
| `PATCH` | 局部修改资源 |
| `DELETE` | 可以携带请求体，但实际接口中较少使用 |
| `GET` | 通常不使用请求体；应优先使用路径参数或查询参数 |

是否真的创建或修改数据，取决于处理函数中的业务逻辑，不是由方法名自动完成的。[FastAPI 请求体说明](https://fastapi.tiangolo.com/tutorial/body/)

## 3. 请求体参数的定义
1. 定义类型
### 使用 Pydantic 描述请求体
FastAPI 通常使用 Pydantic 模型声明 JSON 请求体：

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float
    description: str | None = None


@app.post("/items")
def create_item(item: Item):
    return item
```

`item: Item` 是关键。因为 `Item` 是 Pydantic 模型，FastAPI 会把它识别为请求体参数。

字段规则：

- `name`：必填字符串。
- `price`：必填浮点数。
- `description`：可选字符串，省略时为 `None`。

请求校验通过后，函数得到的是 `Item` 对象，可以读取 `item.name`、`item.price`。FastAPI 还会把模型结构加入 `/docs` 和 OpenAPI 文档。


## 4. 发送请求

在 PyCharm 的 `.http` 文件中可以这样调用：

```http
POST http://127.0.0.1:8000/items
Content-Type: application/json

{
  "name": "notebook",
  "price": 12.5
}
```

也可以打开 `http://127.0.0.1:8000/docs`，找到 `POST /items`，点击 **Try it out** 后填写 JSON。

预期响应：

```json
{
  "name": "notebook",
  "price": 12.5,
  "description": null
}
```

当前示例只是校验并返回数据，没有保存到数据库。

## 5. 校验失败

例如发送：

```json
{
  "name": "notebook",
  "price": "abc"
}
```

`abc` 无法转换为浮点数，FastAPI 默认返回 `422`，处理函数不会执行。错误信息会指出问题位于请求体的 `price` 字段。

## 6. 请求处理过程

```text
客户端发送 JSON 请求体
        ↓
FastAPI 读取 Content-Type 和请求体
        ↓
Pydantic 按 Item 模型转换、校验数据
        ↓
校验成功：调用 create_item(item)
校验失败：返回 422
```

本篇先掌握一个结论：**将 Pydantic 模型写成路径操作函数的参数，就可以声明一个 JSON 请求体。**
