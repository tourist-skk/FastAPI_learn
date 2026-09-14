# 03 · FastAPI 路由与 Python 装饰器

上一篇：[02 · FastAPI 安装与第一步使用](../02-FastAPI安装/02-FastAPI安装与第一步使用.md)

前面已经运行过 `@app.get("/")`。这一篇从它背后的 Python 装饰器语法讲起，理解接口如何登记、请求如何找到函数，以及多个路由如何组织。请求参数从下一篇开始单独学习。

阅读时可以先逐段理解；第 7 节提供可直接复制运行的完整练习，前面的局部示例不需要全部拼到同一个文件中。

## 1. 路由把请求交给哪个函数？

路由时URL地址和处理函数之间的映射关系

在 FastAPI 中，我们通常通过 **HTTP 请求方法与路径** 来定义一个接口。例如：

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/hello")
def say_hello():
    return {"message": "你好！"}
```

客户端发送 `GET /hello` 后，FastAPI 找到登记的 `say_hello` 函数，执行函数并生成响应。官方把这种“路径 + HTTP 方法”的声明称为 **路径操作（Path Operation）**。[FastAPI 第一阶段教程](https://fastapi.tiangolo.com/tutorial/first-steps/)

| 部分 | 在示例中的含义 |
| --- | --- |
| `app` | FastAPI 应用对象 |
| `.get` | 这个接口接受 GET 请求 |
| `"/hello"` | 接口的路径 |
| `@app.get("/hello")` | 将下方函数登记为该接口的处理函数 |
| `say_hello` | Python 函数名，可以与 URL 中的名称不同 |
| `return {...}` | 处理结果，示例中的字典会被转换为 JSON 响应 |

路由装饰器中只写路径，例如 `/hello`，不要写协议、主机名和端口。

## 2. Python 函数也可以作为参数

要理解装饰器，先区分“函数对象”和“调用函数”：

```python
def greet():
    return "你好"


another_name = greet

print(another_name())
```

这里的 `greet` 是函数对象，赋值时没有执行函数。`another_name()` 才真正调用函数，输出 `你好`。

同样，我们也可以把函数交给另一个函数处理：

```python
def run_once(func):
    return func()


def greet():
    return "你好"


print(run_once(greet))
```

`run_once` 接收 `greet` 这个函数，在内部调用它。装饰器也利用了“函数可以被传递、被返回”这一点。

## 3. Python 装饰器是什么？

函数装饰器接收一个函数，并返回一个对象，Python 会把返回结果重新绑定到原来的函数名上。常见用途包括添加日志、缓存结果，或者把函数登记到某个系统中。[Python 函数定义与装饰器](https://docs.python.org/3/reference/compound_stmts.html#function-definitions)

### 3.1 用一个包装函数的例子理解

```python
from functools import wraps


def log_call(func):
    @wraps(func)#wraps:将原函数的属性复制到 wrapper函数上
    def wrapper(*args, **kwargs):
        print("开始调用")
        result = func(*args, **kwargs)
        print("调用结束")
        return result
    # log_call(greet) 返回 wrapper(greet) 
    # 然后开始执行: 开始调用 wrapper -> func即 greet -> print 调用结束
    return wrapper


@log_call
def greet(name: str):
    return f"你好，{name}！"


print(greet("Alice"))
```

预期输出：

```text
开始调用
调用结束
你好，Alice！
```

`log_call` 接收原函数，返回新的 `wrapper` 函数。之后调用 `greet("Alice")`，实际先进入 `wrapper`，再由它调用原函数。

`*args` 接收位置参数，`**kwargs` 接收关键字参数，方便把参数继续传给原函数。`@wraps(func)` 用来保留原函数的名称、文档说明等元信息。[functools.wraps](https://docs.python.org/3/library/functools.html#functools.wraps)

### 3.2 `@` 语法相当于做了什么？

上面的装饰部分：

```python
@log_call
def greet(name: str):
    return f"你好，{name}！"
```

可以理解为下面的写法：

```python
def greet(name: str):
    return f"你好，{name}！"


greet = log_call(greet)
```

装饰动作在执行函数定义时发生。之后每次调用 `greet`，执行的是装饰结果；不会每次都重新执行 `log_call(greet)`。[Python 装饰器语义](https://docs.python.org/3/reference/compound_stmts.html#function-definitions)

这样确实可以理解为装饰作用。每当调用greet时，都要先进行 log_call 装饰

上面是普通同步函数的教学例子，先用它理解语法即可。它尚未处理异步函数，不要直接当作通用 FastAPI 请求日志方案。

## 4. FastAPI 的路由装饰器如何工作？

### 4.1 `@app.get("/hello")` 有两层调用

看这段代码：

```python
@app.get("/hello")
def say_hello():
    return {"message": "你好！"}
```

可以用下面的写法理解其效果（假定 `app` 已创建）：

```python
def say_hello():
    return {"message": "你好！"}


route_decorator = app.get("/hello")
say_hello = route_decorator(say_hello)
```

先调用 `app.get("/hello")`，取得一个知道路径和方法的装饰器；再把 `say_hello` 交给它，完成登记。

FastAPI 的路由装饰器会把函数保存为路由的处理函数，并返回原函数。**装饰器不一定要创建包装函数；完成登记也是一种用途。** 这一行为可以在 [APIRouter 的 `api_route` 实现](https://fastapi.tiangolo.com/reference/apirouter/#fastapi.APIRouter.api_route)中看到。

### 4.2 登记路由与处理请求发生在不同时间

| 时机 | 发生什么 |
| --- | --- |
| 应用加载模块、执行路由定义时 | 执行装饰器，把方法、路径和函数登记到应用中 |
| 客户端发来匹配的请求时 | 匹配路由，读取并校验参数，然后调用处理函数 |
| 函数返回后 | 框架处理返回值并发送 HTTP 响应 |

因此，`@app.get(...)` 不会在登记接口时就执行 `say_hello()`。启用开发模式自动重载后，重新加载应用会再次执行这些路由定义。

```mermaid
flowchart LR
    A[加载模块] --> B[装饰器登记路由]
    B --> C[应用等待请求]
    C --> D[按方法和路径匹配]
    D --> E[读取与校验参数]
    E --> F[调用处理函数]
    F --> G[生成响应]
```

也可以不用装饰器，显式登记同一个接口：

```python
from fastapi import FastAPI

app = FastAPI()


def say_hello():
    return {"message": "你好！"}


app.add_api_route("/hello", say_hello, methods=["GET"])
```

这里传入的是 `say_hello`，不是 `say_hello()`。装饰器与显式登记是两种替代写法，练习时选择一种即可。[FastAPI 路由注册接口](https://fastapi.tiangolo.com/reference/fastapi/#fastapi.FastAPI.add_api_route)

## 5. 路由的定义方式

### 5.1 HTTP 方法也是接口的一部分

| 方法 | FastAPI 写法 | 常见用途 |
| --- | --- | --- |
| GET | `@app.get("/items")` | 查询商品 |
| POST | `@app.post("/items")` | 提交数据或创建商品 |
| PUT | `@app.put("/items")` | 整体替换商品数据 |
| PATCH | `@app.patch("/items")` | 局部修改商品数据 |
| DELETE | `@app.delete("/items")` | 删除商品 |

这些是方法的常见语义；具体业务操作仍由函数实现，写上 `@app.delete` 不会自动删除数据库记录。FastAPI 还提供 `options`、`head` 等声明方式。[HTTP 方法与路径操作](https://fastapi.tiangolo.com/tutorial/first-steps/#operation)

同一个路径可以分别定义 GET 和 POST：

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/items")
def list_items():
    return {"action": "查询商品"}


@app.post("/items")
def submit_item():
    return {"action": "提交商品"}
```

两者的路径相同，方法不同，所以是两个接口。浏览器地址栏直接访问这里会发送 GET 请求；POST 可以用 `/docs` 或 `.http` 文件发起。

路径参数及其匹配顺序将在下一篇 [04 · FastAPI 参数简介与路径参数](../04-FastAPI参数/04-FastAPI参数简介与路径参数.md) 中说明。

## 6. 给路由添加文档说明

路由装饰器除了路径，还可以接收配置：

```python
@app.get("/health", tags=["系统"], summary="检查服务状态")
def check_health():
    """返回服务的基本运行状态。"""
    return {"status": "ok"}
```

| 配置 | 作用 |
| --- | --- |
| `tags=["系统"]` | 在 `/docs` 中给接口分组 |
| `summary="检查服务状态"` | 设置简短的接口说明 |
| 函数文档字符串 | 提供更详细的接口描述 |
| `status_code=201` | 设置正常返回的默认 HTTP 状态码，例如用于创建成功 |
| `response_model=某个模型` | 声明响应结构，参与响应校验、字段过滤和文档生成 |

这些配置写在装饰器中。[路径操作配置](https://fastapi.tiangolo.com/tutorial/path-operation-configuration/)、[响应模型](https://fastapi.tiangolo.com/tutorial/response-model/)

普通 `def` 和 `async def` 都可以作为路由处理函数，路由定义方式相同。异步函数应写成完整的 `async def`，不能只把 `def` 换成 `async`。如何选择同步和异步，可以在后续并发章节学习。

## 7. 完整练习：路由与 HTTP 方法

在本章目录 `03-FastAPI路由/` 中新建 `routes_demo.py`，写入下面的完整代码：

```python
from fastapi import FastAPI
app = FastAPI(title="03 · FastAPI 路由练习")


@app.get("/", tags=["首页"], summary="查看欢迎信息")
def read_home():
    return {"message": "开始学习路由"}


@app.get("/health", tags=["系统"], summary="检查服务状态")
def check_health():
    return {"status": "ok"}


@app.get("/items", tags=["商品"])
def list_items():
    return {"action": "查询商品"}


@app.post("/items", tags=["商品"])
def create_item():
    return {"action": "创建商品"}
```

这个例子暂时没有接收参数，也没有数据库操作。它只用来观察路由、HTTP 方法和文档分组。

### 7.1 启动本章应用

项目已经声明 `fastapi[standard]`。从项目根目录进入本章目录，再启动：

```bash
cd 03-FastAPI路由
uv run fastapi dev routes_demo.py --port 8003
```

这里显式使用 `8003` 端口，便于辨认本章服务。浏览器访问 `http://127.0.0.1:8003/docs`，应看到“首页”“系统”“商品”三个分组。

注意这次文件名是 `routes_demo.py`，不是项目根目录的 `main.py`。服务会加载命令指定的文件。

### 7.2 用 `.http` 文件练习

在本章目录新建 `test_routes.http`，通过 PyCharm HTTP Client 运行：

```http
### 查看服务状态
GET http://127.0.0.1:8003/health

### 查询商品
GET http://127.0.0.1:8003/items

### 同一路径，使用 POST
POST http://127.0.0.1:8003/items
```

| 请求 | 预期状态码 | 预期响应或现象 |
| --- | --- | --- |
| `GET /health` | `200` | `{"status":"ok"}` |
| `GET /items` | `200` | `{"action":"查询商品"}` |
| `POST /items` | `200` | `{"action":"创建商品"}` |
| `GET /unknown` | `404` | 没有对应路径 |
| `DELETE /items` | `405` | 有这个路径，但没有为它定义 DELETE 方法 |

这组练习帮助区分两件事：有没有对应路径，以及请求方法是否支持。

## 8. 接口多了以后：认识 APIRouter

当用户、商品、订单等接口越来越多，可以使用 `APIRouter` 组织一组相关路由，再通过 `include_router` 加入主应用。下面是可以独立运行的简化示例：

```python
from fastapi import APIRouter, FastAPI

app = FastAPI()
users_router = APIRouter(prefix="/users", tags=["用户"])


@users_router.get("/me")
def read_current_user():
    return {"user_id": "current-user"}


app.include_router(users_router)
```

最终路径由前缀 `/users` 和路由路径 `/me` 组合而成，即 `GET /users/me`。`tags` 只负责文档分组，`prefix` 才会改变路径。必须把 router 加入主应用，请求才能通过主应用访问这些接口。[APIRouter 与多文件组织](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

后续可以把 `users_router` 放进单独的 Python 模块，主应用导入后执行 `include_router`。本篇先理解职责：`FastAPI` 是应用入口，`APIRouter` 用于组织相关路由。

## 9. 动手巩固

1. 在第 7 节的应用中增加 `DELETE /items`，返回 `{"action":"删除商品"}`，然后刷新 `/docs` 检查新接口。
2. 把 `read_home` 函数改名为 `welcome`，保持装饰器不变。验证 URL 仍然是 `/`。
3. 为 `GET /health` 添加更详细的函数文档字符串，观察 `/docs` 的变化。
4. 用自己的话解释 `say_hello` 和 `say_hello()` 的区别，以及路由为什么需要保存前者。

完成练习后，在运行服务的终端按 `Ctrl+C` 停止应用。下一篇：[04 · FastAPI 参数简介与路径参数](../04-FastAPI参数/04-FastAPI参数简介与路径参数.md)。
