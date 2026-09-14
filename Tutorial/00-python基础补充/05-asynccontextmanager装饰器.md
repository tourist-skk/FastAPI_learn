# 05-asynccontextmanager装饰器

本篇承接[上下文管理器](04-上下文管理器.md)，通过函数与手写类的对照解释 `yield` 和 FastAPI 生命周期。数据库片段沿用第 16 节的 `Base`、`engine`；使用 `FastAPI` 类型前需导入：

```python
from fastapi import FastAPI
```

## 1. 它的作用

`asynccontextmanager` 来自 Python 标准库 `contextlib`：

```python
from contextlib import asynccontextmanager
```

它是一个装饰器，可以把“包含一个 `yield` 的异步生成器函数”转换成异步上下文管理器工厂，从而省去手动编写 `__aenter__()` 和 `__aexit__()`。

`@装饰器` 写法：

```python
@asynccontextmanager
async def lifespan(app):
    yield
```

近似等于先定义函数，再把函数交给装饰器：

```python
async def lifespan(app):
    yield


lifespan = asynccontextmanager(lifespan)
```

装饰器不会在定义函数时执行启动代码。FastAPI 启动并调用 `lifespan(app)` 后，才会创建和使用对应的异步上下文管理器。

## 2. 与手写异步上下文管理器类的对比

`@asynccontextmanager` 的作用可以理解为：把包含 `yield` 的异步生成器函数转换成实现了 `__aenter__()` 和 `__aexit__()` 协议的对象，从而省去手动编写类的代码。

项目中的写法：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        yield
    finally:
        # 关闭时执行
        await engine.dispose()
```

大致相当于手动编写下面的类：

```python
class Lifespan:
    def __init__(self, app: FastAPI):
        self.app = app

    async def __aenter__(self):
        # 对应 yield 之前的代码
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        # 原函数没有在 yield 后面提供值，因此返回 None
        return None

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        # 对应 finally 中的退出清理代码
        await engine.dispose()

        # 不吞掉上下文中的异常
        return False
```

如果要直接使用这个手写类，可以这样写：

```python
app = FastAPI(lifespan=Lifespan)
```

FastAPI 启动时会调用 `Lifespan(app)` 创建上下文管理器对象。这是为了帮助理解的近似对照；`asynccontextmanager` 还会负责处理生成器、`yield` 返回值以及上下文中的异常。

因此，`@asynccontextmanager` 并不是 FastAPI 专属语法。它是 Python 标准库提供的装饰器，主要用于减少手写异步上下文管理器类的重复代码。

## 3. `yield` 前后的作用

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("应用启动前")

    yield

    print("应用关闭时")
```

`yield` 会暂停函数，并把控制权交给使用上下文管理器的代码：

- `yield` 之前：进入上下文时执行。
- `yield`：应用开始处理请求。
- `yield` 之后：退出上下文时继续执行。

在 `@asynccontextmanager` 管理的函数中，必须执行且只能执行一次 `yield`。

## 4. FastAPI 中的实际执行顺序

当前项目代码可以写成：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. FastAPI 启动时执行
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        # 2. 暂停 lifespan，FastAPI 开始处理请求
        yield
    finally:
        # 3. FastAPI 关闭时继续执行
        await engine.dispose()
```

完整顺序如下：

1. FastAPI 调用 `lifespan(app)`。
2. 进入生命周期上下文。
3. 执行 `yield` 前的建表代码。
4. 运行到 `yield` 后暂停，FastAPI 开始处理请求。
5. 应用收到关闭信号后，FastAPI 退出生命周期上下文。
6. `lifespan` 从 `yield` 后继续运行，释放数据库引擎资源。

把清理代码放在 `finally` 中，可以明确表示：应用退出或运行过程出现异常时，都应该执行资源清理。

## 5. 这段代码中有两个异步上下文管理器

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()
```

不要把它们混在一起：

- `lifespan(app)`：管理整个 FastAPI 应用从启动到关闭的生命周期。
- `engine.begin()`：只管理缩进代码范围内的一次数据库连接和事务。

参考资料：

- [Python asynccontextmanager 文档](https://docs.python.org/3.11/library/contextlib.html#contextlib.asynccontextmanager)
- [FastAPI Lifespan 文档](https://fastapi.tiangolo.com/advanced/events/)
