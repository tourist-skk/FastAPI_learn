# 14 · FastAPI 依赖注入

## 1. 定义

依赖注入（Dependency Injection）是指路径操作函数只声明自己需要什么数据或对象，由 FastAPI 负责调用对应的依赖，并把结果传入函数。

依赖可以是普通函数、异步函数、可调用对象或带 `yield` 的函数。常见用途包括复用查询参数、获取当前用户、权限校验、创建数据库会话等。[FastAPI 依赖注入文档](https://fastapi.tiangolo.com/tutorial/dependencies/)

大部分情况，这么做是为了减少代码冗余

## 2. 实现原理

`Depends()` 用于声明依赖。它接收一个可调用对象，但不会在声明时立即执行。

请求到达后，FastAPI 会：

1. 分析路由所声明的依赖和子依赖，建立依赖关系。
2. 从请求中提取依赖所需的路径参数、查询参数、请求头等数据。
3. 先执行子依赖，再执行外层依赖。
4. 把依赖函数的返回值注入路径操作函数。
5. 所有依赖成功后，再执行路径操作函数。

同一个依赖在一次请求中被多处使用时，FastAPI 默认只执行一次，并复用缓存结果。需要每次重新执行时，可以设置 `Depends(dependency, use_cache=False)`。

## 3. 方式一：通过函数参数接收依赖结果

下面把公共的查询参数提取为一个依赖，并在两个接口中复用：

```python
from fastapi import Depends, FastAPI, Query

app = FastAPI()


def common_parameters(
    q: str | None = Query(default=None, max_length=50),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=60),
) -> dict:
    return {
        "q": q,
        "skip": skip,
        "limit": limit,
    }

@app.get("/items")
def get_items(
    params: dict = Depends(common_parameters),
):
    return {"resource": "items", **params}


@app.get("/users")
def get_users(
    params: dict = Depends(common_parameters),
):
    return {"resource": "users", **params}
```

### 3.1 参数解释

`q`、`skip` 和 `limit` 是依赖函数的参数。FastAPI 会像处理路由参数一样，从当前请求的查询参数中获取并校验它们。

`params` 是路径操作函数接收依赖结果的参数名。请求到达时，FastAPI 会把 `common_parameters()` 返回的字典传给它。

`params: dict` 表示依赖结果应当是字典；`= Depends(common_parameters)` 表示这个参数的值由 `common_parameters` 提供。

传给 `Depends()` 的是函数对象 `common_parameters`，因此不加括号。函数会在请求处理期间由 FastAPI 调用。

### 3.2 加入依赖注入的好处

如果没有依赖注入，`q`、`skip`、`limit` 以及它们的校验规则需要在 `get_items()` 和 `get_users()` 中重复声明。提取依赖后，两条路由共用一份代码。

依赖函数还把“解析分页参数”和“处理业务数据”分开了。以后修改 `limit` 的默认值或 `q` 的长度限制时，只需要修改 `common_parameters()`。

依赖中声明的 Query、Header 等请求参数也会自动出现在 OpenAPI 和 `/docs` 中。

## 4. 方式二：在装饰器中声明依赖

有些依赖只需要执行校验，不需要在路由函数中使用返回值。这时可以使用装饰器的 `dependencies` 参数：

```python
from fastapi import Header, HTTPException, status


def verify_token(
    x_token: str = Header(),
) -> None:
    if x_token != "secret-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的访问令牌",
        )


@app.get(
    "/admin",
    dependencies=[Depends(verify_token)],
)
def get_admin_data():
    return {"message": "管理员数据"}
```

`dependencies` 接收一个 `Depends()` 列表。FastAPI 会执行列表中的依赖，但不会把其返回值传给路由函数。

`x_token` 使用 `Header()` 声明，因此对应请求头 `X-Token`。校验失败时抛出异常，`get_admin_data()` 不会执行。

这种方式适合权限检查、日志记录等只关心是否成功执行的依赖，也能避免路由函数中出现未使用的参数。

## 5. 方式三：路由组依赖和全局依赖

### 5.1 路由组依赖

把依赖声明在 `APIRouter` 上，可以让一组路由共同使用它：

```python
from fastapi import APIRouter

admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(verify_token)],
)


@admin_router.get("/stats")
def get_admin_stats():
    return {"online_users": 100}


app.include_router(admin_router)
```

只有加入 `admin_router` 的路由会执行 `verify_token`。

### 5.2 全局依赖

如果整个应用的所有路由都需要同一个依赖，可以在创建应用时声明：

```python
secure_app = FastAPI(
    dependencies=[Depends(verify_token)],
)


@secure_app.get("/profile")
def get_profile():
    return {"username": "Alice"}
```

访问 `secure_app` 中的任何路径操作时，都会先执行 `verify_token`。实际项目通常在路由级、路由组级和应用级之间选择合适的作用范围。

## 6. 方式四：使用 `yield` 管理资源

数据库会话、文件和网络连接等资源需要在使用后释放。依赖函数可以使用 `yield` 把资源交给路由，并在请求结束时执行清理代码：

```python
from collections.abc import Iterator


class DatabaseSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def get_session() -> Iterator[DatabaseSession]:
    session = DatabaseSession()

    try:
        yield session
    finally:
        session.close()


@app.get("/session")
def check_session(
    session: DatabaseSession = Depends(get_session),
):
    return {"session_closed": session.closed}
```

`yield` 之前负责创建资源，`yield` 的值会注入 `session`，`finally` 中的代码负责保证资源最终被关闭。

## 7. 执行时机

普通依赖的基本执行顺序是：

```text
中间件：请求阶段
→ 子依赖
→ 当前依赖
→ 路径操作函数
→ 中间件：响应阶段
```

带 `yield` 的依赖还包含退出代码：

- 默认的 `Depends(get_session)` 使用 `scope="request"`。`yield` 后的清理代码在中间件响应阶段之后、响应发送完成后执行。
- `Depends(get_session, scope="function")` 会在路径操作函数结束后、响应发送前执行清理代码；因此它也早于中间件的响应阶段。

资源需要贯穿整个响应过程时使用默认的 `request` 范围；路由函数结束后就不再需要该资源时，可以使用 `function` 范围。[`yield` 依赖的执行范围](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#early-exit-and-scope)

## 8. 依赖注入与中间件的区别

### 8.1 依赖注入

依赖注入属于路由处理的一部分，可以应用于单个路由、一个 `APIRouter` 或整个应用。它能读取并校验参数、返回对象给路由使用，并把参数要求写入接口文档。

适合获取当前用户、权限检查、公共查询参数和数据库会话等与路由业务有关的功能。

### 8.2 中间件

中间件包裹在依赖和路由外层，会处理经过应用的 HTTP 请求和响应。它可以修改请求或响应，也可以不调用 `call_next` 而直接返回响应，但不会把返回值作为函数参数注入路由。

适合访问日志、统一耗时统计、跨域和响应压缩等与整个 HTTP 请求过程有关的功能。

### 8.3 选择方法

路由函数需要使用某个结果时，通常选择依赖注入。逻辑需要同时包裹请求和响应，或者应在路由匹配前处理时，通常选择中间件。

**记忆：`Depends()` 声明路由需要什么，由 FastAPI 负责执行依赖并把结果传入；中间件则负责包裹整个请求和响应过程。**
