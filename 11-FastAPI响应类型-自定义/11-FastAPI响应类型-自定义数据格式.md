# 11 · FastAPI 响应类型：自定义数据格式

## 1. 定义

自定义数据格式是指使用 Pydantic 模型定义响应数据的字段和类型，再让 FastAPI 按照该模型输出数据。

Pydantic 是 FastAPI 的核心依赖，用于数据校验和序列化。

这里自定义的是响应的**数据结构**，默认响应格式仍然是 JSON：

```http
Content-Type: application/json
```

## 2. 实现原理

`response_model` 是路径操作装饰器的参数。它接收一个 Pydantic 模型，并用该模型处理路径操作函数返回的数据。

处理过程如下：

1. 路径操作函数返回字典、列表或模型对象。
2. FastAPI 使用响应模型校验返回数据。
3. 只保留响应模型中声明的字段。
4. 将数据序列化为 JSON。
5. 在 OpenAPI 和 `/docs` 中生成响应结构说明。

如果返回的数据不符合模型要求，说明服务端代码返回了错误的数据，FastAPI 会产生响应校验错误，而不是把错误数据发送给客户端。[响应模型官方文档](https://fastapi.tiangolo.com/tutorial/response-model/)

## 3. 方式一：使用 `response_model`

### 3.1 返回单个模型

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class UserCreate(BaseModel):
    username: str
    password: str
    nickname: str | None = None


class UserPublic(BaseModel):
    username: str
    nickname: str | None = None


@app.post("/users", response_model=UserPublic)
def create_user(user: UserCreate):
    return user.model_dump()
```

请求体中包含 `password`，但 `UserPublic` 没有声明该字段，因此最终响应会过滤掉密码：

```json
{
  "username": "Alice",
  "nickname": null
}
```

`response_model` 适合函数实际返回字典或数据库对象，但接口需要按照指定结构输出数据的场景。这里先用 `model_dump()` 将输入模型转换为字典，再由响应模型过滤敏感字段。

### 3.2 返回模型列表

`response_model` 也可以接收 `list[模型类]`：

```python
@app.get("/users", response_model=list[UserPublic])
def get_users():
    return [
        {"username": "Alice", "nickname": "A"},
        {"username": "Bob", "nickname": None},
    ]
```

FastAPI 会分别校验和序列化列表中的每一项。

## 4. 方式二：使用函数返回类型注解

当函数实际返回的就是响应模型对象时，可以直接标注返回类型：

```python
@app.get("/profile")
def get_profile() -> UserPublic:
    return UserPublic(
        username="Alice",
        nickname="A",
    )
```

FastAPI 会把 `UserPublic` 当作响应模型，同样执行校验、序列化、字段过滤和文档生成。

这种方式能让编辑器和类型检查工具同时检查函数的返回值，适合实际返回类型与响应模型一致的场景。

## 5. 两种方式的区别

### 5.1 使用 `response_model` 的场景

当函数内部处理的数据类型与对外响应类型不一致时，使用 `response_model` 更合适。例如函数接收 `UserCreate`，但接口只能向客户端公开 `UserPublic` 中的字段。

### 5.2 使用返回类型注解的场景

当函数实际返回的就是 `UserPublic` 对象时，使用 `-> UserPublic` 更直接，还能获得编辑器的类型提示。

如果同时声明返回类型注解和 `response_model`，FastAPI 会优先使用 `response_model`。

## 6. 排除值为空的字段

如果不希望响应中出现值为 `None` 的字段，可以使用 `response_model_exclude_none=True`：

```python
@app.get(
    "/profile/simple",
    response_model=UserPublic,
    response_model_exclude_none=True,
)
def get_simple_profile():
    return {"username": "Alice", "nickname": None}
```

最终响应为：

```json
{
  "username": "Alice"
}
```

**记忆：Pydantic 模型负责定义响应结构，`response_model` 或返回类型注解负责告诉 FastAPI 使用哪个响应模型。**
