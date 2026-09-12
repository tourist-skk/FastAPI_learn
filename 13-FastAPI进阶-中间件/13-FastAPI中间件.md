# 13 · FastAPI 中间件

## 1. 定义

中间件（Middleware）是包裹在路由外层的一段公共处理逻辑。每个请求到达具体路由之前会经过中间件，路由生成的响应也会再次经过中间件，然后才返回客户端。

中间件常用于记录日志、统计耗时、添加响应头、身份校验、跨域处理和响应压缩等。[FastAPI 中间件文档](https://fastapi.tiangolo.com/tutorial/middleware/)

## 2. 实现原理

中间件把应用一层层包裹起来。它既可以把请求继续交给下一层，也可以直接返回响应，提前终止请求。

一次普通请求的执行过程是：

```text
客户端请求
  → 中间件的请求阶段
  → 路由函数
  → 中间件的响应阶段
  → 客户端收到响应
```

`await call_next(request)` 是请求和响应两个阶段的分界线：

- 它之前的代码在路由执行前运行。
- 它会把请求交给下一层，并等待响应。
- 它之后的代码在路由生成响应后运行。

## 3. 方式一：函数式中间件

使用 `@app.middleware("http")` 可以定义处理 HTTP 请求的中间件：

```python
import time

from fastapi import FastAPI, Request, Response

app = FastAPI()


@app.middleware("http")
async def add_process_time(
    request: Request,
    call_next,
) -> Response:
    start_time = time.perf_counter()

    response = await call_next(request)

    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.6f}"
    return response


@app.get("/hello")
def hello():
    return {"message": "Hello"}
```

### 3.1 函数参数解释

`request: Request` 表示当前请求，可以读取请求方法、URL、请求头等信息，例如 `request.method` 和 `request.url.path`。

`call_next` 是 FastAPI 传入的异步函数。调用 `await call_next(request)` 后，请求会继续进入下一层中间件或路由，并返回一个响应对象。

`response: Response` 是后续处理生成的响应。返回客户端之前，可以修改它的响应头等信息。中间件函数最后必须返回响应对象。

### 3.2 执行时机

上例中，记录 `start_time` 发生在路由执行前；计算耗时和添加响应头发生在路由执行后。

如果中间件没有调用 `call_next`，而是直接返回一个 `Response`，路由函数就不会执行。这种写法可以用于拒绝不合法的请求。

使用 `yield` 的依赖项，其退出代码在中间件完成后运行；后台任务也会在所有中间件完成后运行。

## 4. 多个中间件的执行顺序

每添加一个中间件，它都会包裹已有的应用。**最后添加的中间件位于最外层。**

```python
from fastapi import FastAPI, Request

order_app = FastAPI()


@order_app.middleware("http")
async def middleware_a(request: Request, call_next):
    print("A：请求阶段")
    response = await call_next(request)
    print("A：响应阶段")
    return response


@order_app.middleware("http")
async def middleware_b(request: Request, call_next):
    print("B：请求阶段")
    response = await call_next(request)
    print("B：响应阶段")
    return response


@order_app.get("/")
def index():
    print("执行路由")
    return {"message": "ok"}
```

`middleware_a` 先添加，`middleware_b` 后添加，因此 B 在最外层。访问一次接口时输出：

```text
B：请求阶段
A：请求阶段
执行路由
A：响应阶段
B：响应阶段
```

请求顺序是“从外到内”，响应顺序是“从内到外”。因此多个中间件整体呈现类似洋葱的结构。

## 5. 方式二：类中间件

需要保存配置或重复使用中间件时，可以继承 `BaseHTTPMiddleware`：

```python
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware


class CustomHeaderMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, header_value: str):
        super().__init__(app)
        self.header_value = header_value

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-App-Name"] = self.header_value
        return response


class_app = FastAPI()

class_app.add_middleware(
    CustomHeaderMiddleware,
    header_value="FastAPI Learn",
)


@class_app.get("/")
def class_index():
    return {"message": "ok"}
```

### 5.1 类中参数解释

`__init__()` 中的 `app` 是被当前中间件包裹的下一层应用，由 FastAPI 自动传入。`header_value` 是注册中间件时传入的自定义配置。

`dispatch()` 是每次 HTTP 请求都会执行的方法。`request` 和 `call_next` 的作用与函数式中间件相同。

`app.add_middleware()` 的第一个参数是中间件类，其余关键字参数会传给该类的 `__init__()`。

## 6. 方式三：使用内置中间件

FastAPI 可以通过 `app.add_middleware()` 注册 Starlette 提供的中间件。例如使用 `GZipMiddleware` 压缩较大的响应：

```python
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

gzip_app = FastAPI()

gzip_app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,
    compresslevel=5,
)


@gzip_app.get("/data")
def get_data():
    return {"content": "a" * 2000}
```

`minimum_size=1000` 表示响应体达到 1000 字节时才考虑压缩；`compresslevel=5` 表示压缩级别，级别越高通常压缩得越小，但需要更多计算时间。

内置中间件适合处理通用需求。除了 GZip，常见的还有跨域处理使用的 `CORSMiddleware`。

## 7. 如何选择

简单的项目内逻辑使用函数式中间件。需要配置、封装和复用时使用类中间件。压缩、跨域等通用功能优先使用框架提供的内置中间件。

**记忆：中间件在 `call_next` 前处理请求，在 `call_next` 后处理响应；最后添加的中间件最先接收请求。**
