# 04 · FastAPI 参数简介与路径参数

上一篇：[03 · FastAPI 路由与 Python 装饰器](../03-FastAPI路由/03-FastAPI路由与Python装饰器.md)

路由决定“哪个函数处理请求”，参数决定“这个函数从请求中得到什么数据”。本篇先认识 FastAPI 中常见的参数来源，再重点学习路径参数。查询参数、请求体等将在后续章节展开。

## 1. 什么是请求参数？

客户端调用接口时，除了 HTTP 方法和路径，还可以携带各种数据。例如：

```text
GET http://127.0.0.1:8000/users/12?detail=true
```

这个地址可以拆成：

| 部分 | 内容 | 含义 |
| --- | --- | --- |
| 协议 | `http` | 使用 HTTP 通信 |
| 主机和端口 | `127.0.0.1:8000` | 服务运行的位置 |
| 路径 | `/users/12` | 要访问的资源位置 |
| 路径参数 | `12` | 路径中变化的数据，例如用户编号 |
| 查询字符串 | `detail=true` | 路径后以 `?` 开始的附加数据 |

FastAPI 会根据路由和函数签名读取这些数据，进行类型转换与校验，再把结果作为实参传给处理函数。

## 2. FastAPI 参数来源简介

一个 HTTP 请求可以从多个位置携带数据：

| 参数来源 | 示例 | 常见用途 |
| --- | --- | --- |
| 路径参数（Path） | `/users/12` 中的 `12` | 指定某个资源 |
| 查询参数（Query） | `/users?keyword=alice` | 搜索、筛选、分页 |
| 请求头（Header） | `Authorization: Bearer ...` | 身份认证、内容协商 |
| Cookie | `session_id=...` | 会话标识 |
| 请求体（Body） | POST 请求中的 JSON | 提交结构化数据 |
| 表单（Form） | 登录表单的用户名和密码 | 接收表单编码数据 |
| 文件（File） | 上传的图片或文档 | 文件上传 |
| 依赖注入（Depends） | 由依赖函数产生的值 | 复用认证、数据库会话等逻辑 |

在常见的简单声明中，FastAPI 会按照以下规则判断来源：[请求体、路径与查询参数](https://fastapi.tiangolo.com/tutorial/body/#request-body-path-query-parameters)

1. 参数名出现在路由路径中，它是路径参数。
2. 参数使用 Pydantic 模型类型，它通常来自请求体。
3. 其他 `str`、`int`、`bool` 等简单类型参数通常是查询参数。

还可以使用 `Path`、`Query`、`Header`、`Cookie`、`Body` 等工具显式声明来源和约束。本篇只深入 `Path`。

参数来源并非由 HTTP 方法单独决定。POST 接口也可以有路径参数和查询参数，GET 接口也可以有请求头参数。

## 3. 定义第一个路径参数

路径参数是在路由路径中使用花括号声明的变量：[FastAPI 路径参数](https://fastapi.tiangolo.com/tutorial/path-params/)

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/users/{user_id}")
def read_user(user_id: int):
    return {"user_id": user_id}
```

调用 `GET /users/12` 时：

1. `/users/{user_id}` 匹配 `/users/12`。
2. FastAPI 取出字符串 `"12"`。
3. 根据 `user_id: int` 将它转换为整数 `12`。
4. FastAPI 调用 `read_user(user_id=12)`。
5. 函数返回字典，响应体为 `{"user_id": 12}`。

路由中的 `{user_id}` 与函数参数 `user_id` 必须同名。函数名 `read_user` 不影响 URL。

### 3.1 路径参数一定存在

只要请求已经匹配 `/users/{user_id}`，就一定有一个路径片段供 `user_id` 使用。因此，路径参数在 URL 层面总是必填的，Swagger UI 也会将它标记为 required。

下面两个地址的结果不同：

| 请求 | 结果 |
| --- | --- |
| `GET /users/12` | 匹配 `/users/{user_id}`，`user_id` 为 `12` |
| `GET /users` | 路径结构不同；如果没有单独定义 `/users`，返回 `404` |

把函数参数写成 `user_id: int | None = None` 也不会让 `/users` 匹配 `/users/{user_id}`。如果两种地址都需要支持，应分别定义 `/users` 和 `/users/{user_id}` 两条路由。

### 3.2 一个路径可以包含多个参数

```python
@app.get("/shops/{shop_id}/items/{item_id}")
def read_shop_item(shop_id: int, item_id: int):
    return {"shop_id": shop_id, "item_id": item_id}
```

请求 `/shops/3/items/18` 时，函数得到 `shop_id=3` 和 `item_id=18`。FastAPI 按参数名对应数据，函数签名中的排列顺序不需要与路径出现顺序一致，但保持相同顺序通常更容易阅读。

## 4. 类型转换与校验

HTTP 路径中的原始值是文本。类型注解告诉 FastAPI 希望得到哪种 Python 数据：[路径参数的数据转换和校验](https://fastapi.tiangolo.com/tutorial/path-params/#path-parameters-with-types)

```python
@app.get("/items/{item_id}")
def read_item(item_id: int):
    return {
        "item_id": item_id,
        "python_type": type(item_id).__name__,
    }
```

请求 `/items/3` 时，函数拿到 Python 整数 `3`，而不是字符串 `"3"`：

```json
{
  "item_id": 3,
  "python_type": "int"
}
```

如果请求 `/items/abc`，路由的形状仍然匹配，但 `abc` 无法转换为整数。FastAPI 默认返回 `422 Unprocessable Content`，错误内容会指出位置 `path`、参数名 `item_id` 和失败原因。处理函数不会执行。

这三种状态需要区分：

| 状态码 | 含义 | 示例 |
| --- | --- | --- |
| `200` | 路由匹配且参数校验通过 | `GET /items/3` |
| `404` | 没有匹配的路径 | `GET /unknown` |
| `422` | 路由匹配，但请求参数校验失败 | `GET /items/abc`，而 `item_id` 要求为整数 |

路径参数也可以声明为 `str`、`float`、`bool`、`UUID`、日期等类型。选择类型时应表达业务数据本身的含义。

## 5. 这里与 Pydantic 有什么关系？

路径参数通常直接写成 `item_id: int`，不需要为一个简单参数创建 `BaseModel`。FastAPI 仍会利用与 Pydantic 集成的数据处理能力完成解析、校验、错误描述和 JSON Schema 生成，并把参数信息写入 OpenAPI 文档。[路径参数与 Pydantic](https://fastapi.tiangolo.com/tutorial/path-params/#pydantic)

可以这样理解：

```text
路径中的文本 "3"
        ↓
按 int 规则解析和校验
        ↓
Python 整数 3
        ↓
传给路径操作函数
```

类型注解同时服务于运行时校验、编辑器提示和自动文档。它不是只写给编辑器看的注释。

## 6. 使用 `Path` 添加约束

FastAPI允许为参数声明额外的信息和校验,Path即可用来给路径参数添加校验和文档信息的工具。它的参数主要分三类：数值约束、字符串约束、文档信息。

参数	含义	示例
gt	greater than，大于	gt=0
ge	greater or equal，大于等于	ge=1
lt	less than，小于	lt=100
min_length	最小字符数	min_length=2
max_length	最大字符数	max_length=20


只有 `int` 类型时，`-1` 仍然是合法整数。如果业务规定商品编号必须为正数，可以使用 `Path` 添加限制：[路径参数数值校验](https://fastapi.tiangolo.com/tutorial/path-params-numeric-validations/)

```python
from typing import Annotated

from fastapi import FastAPI, Path

app = FastAPI()


@app.get("/items/{item_id}")
def read_item(
    item_id: Annotated[
        int,
        Path(title="商品编号", description="取值范围为 1 到 10000", ge=1, le=10000),
    ],
):
    return {"item_id": item_id}
```

`Annotated` 的第一个值是实际类型，后面的 `Path(...)` 为它添加校验和文档元数据。

| 约束 | 含义 |
| --- | --- |
| `gt=0` | 大于 0 |
| `ge=1` | 大于或等于 1 |
| `lt=100` | 小于 100 |
| `le=100` | 小于或等于 100 |
| `min_length=2` | 字符串至少 2 个字符 |
| `max_length=20` | 字符串最多 20 个字符 |
| `pattern="..."` | 字符串符合指定正则表达式 |

约束要与参数类型和业务规则相符。上面的 `item_id` 接受 `1` 和 `10000`，拒绝 `0`、负数、超过上限的整数以及不能解析为整数的文本。

## 7. 固定路径与动态路径的顺序

路径参数会匹配相应位置上的各种文本，因此固定路径要放在可能与它冲突的动态路径前面：[路由顺序](https://fastapi.tiangolo.com/tutorial/path-params/#order-matters)

```python
@app.get("/users/me")
def read_current_user():
    return {"user_id": "current-user"}


@app.get("/users/{user_id}")
def read_user(user_id: int):
    return {"user_id": user_id}
```

按照这个顺序：

- `/users/me` 进入 `read_current_user`。
- `/users/12` 进入 `read_user`。

如果把 `/users/{user_id}` 放在前面，请求 `/users/me` 会先匹配动态路由，随后因为 `me` 不能转换为整数而返回 `422`。`int` 类型校验发生在路由匹配之后，不会使路由器跳到后面的 `/users/me`。

FastAPI 按声明顺序检查这些路由，固定路径不会自动获得更高优先级。也应避免重复声明相同方法和相同路径，并期望后面的函数覆盖前面的函数。

## 8. 限制为几个预定义值

如果路径参数只允许几个固定值，可以使用字符串枚举：[预定义路径参数](https://fastapi.tiangolo.com/tutorial/path-params/#predefined-values)

```python
from enum import Enum

from fastapi import FastAPI

app = FastAPI()


class ModelName(str, Enum):
    alexnet = "alexnet"
    resnet = "resnet"
    lenet = "lenet"


@app.get("/models/{model_name}")
def read_model(model_name: ModelName):
    return {"model_name": model_name}
```

`/models/resnet` 可以通过校验，`/models/unknown` 默认返回 `422`。Swagger UI 会把三个合法值显示为可选项。继承 `str` 可以使枚举值与 API 中的字符串良好配合。

## 9. 接收包含斜杠的路径

普通路径参数只占一个路径片段，所以 `/files/{file_path}` 无法把 `docs/guide.md` 整体作为一个参数。需要接收完整子路径时，可以使用 Starlette 的 `path` 转换器：[包含路径的路径参数](https://fastapi.tiangolo.com/tutorial/path-params/#path-parameters-containing-paths)

```python
@app.get("/files/{file_path:path}")
def read_file(file_path: str):
    return {"file_path": file_path}
```

请求 `/files/docs/guide.md` 时，`file_path` 的值是 `"docs/guide.md"`。

这里演示的是读取 URL 中的文本，并没有真的访问磁盘。实际提供文件下载时，还需要处理访问权限、路径规范化等问题。

## 10. 完整练习

在 `04-FastAPI参数/` 中新建 `path_params_demo.py`：

```python
from enum import Enum
from typing import Annotated

from fastapi import FastAPI, Path

app = FastAPI(title="04 · 路径参数练习")


class ModelName(str, Enum):
    alexnet = "alexnet"
    resnet = "resnet"
    lenet = "lenet"


@app.get("/users/me", tags=["用户"])
def read_current_user():
    return {"user_id": "current-user"}


@app.get("/users/{user_id}", tags=["用户"])
def read_user(user_id: int):
    return {"user_id": user_id}


@app.get("/items/{item_id}", tags=["商品"])
def read_item(
    item_id: Annotated[int, Path(ge=1, le=10000, description="商品编号")],
):
    return {"item_id": item_id}


@app.get("/shops/{shop_id}/items/{item_id}", tags=["商品"])
def read_shop_item(shop_id: int, item_id: int):
    return {"shop_id": shop_id, "item_id": item_id}


@app.get("/models/{model_name}", tags=["模型"])
def read_model(model_name: ModelName):
    return {"model_name": model_name}


@app.get("/files/{file_path:path}", tags=["文件"])
def read_file(file_path: str):
    return {"file_path": file_path}
```

从项目根目录执行：

```bash
cd 04-FastAPI参数
uv run fastapi dev path_params_demo.py --port 8004
```

打开 `http://127.0.0.1:8004/docs`，观察每个路径参数的类型、必填状态、约束和枚举选项。

还可以新建 `test_path_params.http`：

```http
### 固定路径
GET http://127.0.0.1:8004/users/me

### 整数路径参数
GET http://127.0.0.1:8004/users/12

### 路径形状匹配，但整数解析失败
GET http://127.0.0.1:8004/users/abc

### 符合范围约束
GET http://127.0.0.1:8004/items/100

### 不符合大于或等于 1 的约束
GET http://127.0.0.1:8004/items/0

### 多个路径参数
GET http://127.0.0.1:8004/shops/3/items/18

### 枚举路径参数
GET http://127.0.0.1:8004/models/resnet

### 包含斜杠的路径参数
GET http://127.0.0.1:8004/files/docs/guide.md
```

预期结果：

| 请求 | 状态码 | 关键结果 |
| --- | --- | --- |
| `/users/me` | `200` | 固定路径正确匹配 |
| `/users/12` | `200` | `user_id` 是整数 `12` |
| `/users/abc` | `422` | 无法解析为整数 |
| `/items/100` | `200` | 满足范围约束 |
| `/items/0` | `422` | 不满足 `ge=1` |
| `/shops/3/items/18` | `200` | 得到两个整数参数 |
| `/models/resnet` | `200` | 枚举值合法 |
| `/models/unknown` | `422` | 不属于枚举值 |
| `/files/docs/guide.md` | `200` | 得到 `docs/guide.md` |

## 11. 常见错误

### 路由变量与函数参数不同名

```python
@app.get("/items/{item_id}")
def read_item(product_id: int):
    return {"product_id": product_id}
```

路径声明了 `item_id`，函数却要求 `product_id`。两者无法正确对应。应统一使用同一个名称。

### 把类型写进花括号

```python
# 错误思路
@app.get("/items/{item_id:int}")
def read_item(item_id: int):
    return {"item_id": item_id}
```

FastAPI 的常规写法是在函数签名中声明 `item_id: int`。`{file_path:path}` 是用于接收完整子路径的特殊转换器语法，不代表常规类型都要写进路由字符串。

### 混淆 404 与 422

`/items` 不符合 `/items/{item_id}` 的路径形状，通常是 `404`；`/items/abc` 符合路径形状，但不满足整数规则，所以是 `422`。

### 动态路径放在固定路径前面

`/users/{user_id}` 如果先声明，可能抢先匹配 `/users/me`。先声明更具体的固定路径。

## 12. 动手巩固

1. 增加 `GET /orders/{order_id}`，将 `order_id` 声明为正整数。
2. 增加 `GET /categories/{category}`，用枚举限制为 `book`、`food`、`tool`。
3. 请求 `/items/-1`、`/items/1` 和 `/items/10001`，比较结果。
4. 暂时交换 `/users/me` 与 `/users/{user_id}` 的声明顺序，观察 `/users/me` 的响应，然后恢复正确顺序。
5. 在 `/docs` 中查看 `item_id`，确认它被标记为路径参数、必填整数，并显示范围约束。

完成练习后，在运行服务的终端按 `Ctrl+C` 停止应用。下一篇可以继续学习查询参数，包括可选参数、默认值、列表参数和字符串约束。
