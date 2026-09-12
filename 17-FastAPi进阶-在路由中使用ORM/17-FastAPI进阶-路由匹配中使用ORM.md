# 17-FastAPI进阶-在路由中使用ORM

核心流程：创建会话工厂 → 定义依赖项 → 使用 `Depends` 将会话交给路由 → 执行查询 → 提交或回滚 → 关闭会话。

## 一、先看完整用法

下面沿用第 16 节的 `app`、`engine` 和 `Book`。可以把代码接在现有 `database_sqlite.py` 的模型和 `app` 定义之后，无需重复创建应用。原笔记中的 `async_engine` 在当前脚本里对应的变量名是 `engine`。

```python
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


# 创建工厂，供不同请求创建各自的数据库会话
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_database():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        # 离开 async with 时自动关闭会话，不必重复调用 close()


@app.get("/book/books")
async def get_book_list(
    db: AsyncSession = Depends(get_database, scope="function")
):
    result = await db.execute(select(Book))
    books = result.scalars().all()
    return books
```

参数说明：

- `bind=engine`：指定会话执行数据库操作时使用的引擎。
- `class_=AsyncSession`：工厂创建的会话类型。默认就是 `AsyncSession`，这里显式写出便于理解。
- `expire_on_commit=False`：提交后不自动将已加载的 ORM 属性标记为过期，方便继续读取；不表示永远不查询数据库，也不保证数据始终最新。
- `Depends(get_database, ...)`：把依赖函数交给 FastAPI 调用，这里不写 `get_database()`。
- `scope="function"`：在路由函数返回后、响应发送前执行依赖的退出代码。本例把 `commit()` 放在 `yield` 后面，所以明确指定这个时机。

`db` 和依赖中的 `session` 指向同一个会话对象，不是复制出来的两份会话。

## 二、为什么可以用于 async with

### 1. 先区分工厂与会话对象

这两行执行的事情不同：

```python
AsyncSessionLocal = async_sessionmaker(bind=engine)
session = AsyncSessionLocal()
```

第一行创建的是**会话工厂**：保存引擎、会话类型等配置，方便重复创建会话。

第二行调用工厂，创建的是一个 **AsyncSession 会话对象**，用于执行 ORM 查询、管理对象和事务。

因此：

```python
async with AsyncSessionLocal() as session:
    ...
```

可以拆开理解为：

```python
session_object = AsyncSessionLocal()

async with session_object as session:
    ...
```

真正进入 `async with` 的是 `session_object`。括号 `()` 很重要，不能直接写成 `async with AsyncSessionLocal:`。

创建会话通常也不会立刻向数据库获取连接；第一次执行 SQL 等需要数据库的操作时，才会通过引擎取得连接。

### 2. AsyncSession 已经实现异步上下文管理协议

`AsyncSession` 类已经提供：

- `__aenter__()`：进入时返回会话自身，所以 `as session` 得到这个会话。
- `__aexit__()`：退出时执行会话关闭逻辑，释放会话占用的资源，并归还借用的连接。

所以不需要自己再给 `AsyncSession` 添加 `@asynccontextmanager`。

可以用下面的简化代码理解协议的作用，实际 SQLAlchemy 实现还包含退出时的取消保护：

```python
class ExampleSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    async def close(self):
        print("释放会话资源")
```

原笔记同时写了 `async with` 和 `finally: await session.close()`。这是重复关闭，因此完整用法中保留 `async with` 自动清理即可。

**自动关闭不等于自动提交。** `async with AsyncSessionLocal()` 负责关闭会话；本例提交成功来自我们显式写出的 `await session.commit()`。关闭时仍未完成的事务会被回滚，不会自动保存修改。[SQLAlchemy 会话与异步上下文说明](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#synopsis-orm)。

## 三、get_database 内部的执行顺序

### 1. 正常情况：创建 → 暂停 → 路由 → 提交 → 关闭

以 `GET /book/books` 为例，按上面 `scope="function"` 的写法执行：

1. FastAPI 收到请求，发现路由参数依赖 `get_database`。
2. FastAPI 调用并开始推进这个含 `yield` 的异步生成器函数。
3. 执行 `AsyncSessionLocal()`，创建本次依赖使用的会话。
4. 进入 `async with`，会话的 `__aenter__()` 返回自身，赋给 `session`。
5. 执行到 `yield session`，把会话交给 FastAPI；`get_database` 暂停，`async with` 仍处于进入状态，会话尚未关闭。
6. FastAPI 将会话赋给路由参数 `db`，再执行路由函数。
7. 路由执行 `await db.execute(select(Book))`，读取结果并 `return books`。
8. FastAPI 恢复依赖函数，从 `yield` 后继续，执行 `await session.commit()`。
9. 没有异常则跳过 `except`；离开 `async with`，自动关闭会话。
10. FastAPI 继续完成响应处理并发送响应。

**`yield session` 不是 `return session`。** `yield` 会保存暂停位置；如果改成 `return`，函数会立即退出 `async with`，路由执行时就无法继续使用这段上下文管理的会话和事务。

查询后调用 `commit()` 不代表插入了书籍。这个依赖采用统一的事务处理方式；纯查询并不需要通过提交来保存查询结果。

### 2. 异常情况：回到 yield 处 → 回滚 → 继续抛出 → 关闭

如果路由中的数据库操作抛出异常，并且没有在路由内部处理：

1. FastAPI 将异常传回依赖中暂停的 `yield session` 位置。
2. 对于匹配 `Exception` 的异常，跳过后面的 `commit()`，转入 `except Exception`。
3. 执行 `await session.rollback()`，撤销本次事务中尚未提交的修改。
4. `raise` 将同一个异常继续抛出，让 FastAPI 的异常处理逻辑处理。
5. 离开 `async with`，会话仍然会被自动关闭。

如果异常发生在 `commit()` 本身，也会进入同一个 `except` 分支。例如，提交时违反数据库唯一约束，就会尝试回滚，再抛出异常。

注意：如果路由捕获异常后只返回一个普通字典，依赖不会知道发生过错误，仍会继续尝试提交。回滚也不能撤销更早已经提交的事务。

### 3. 加上打印，观察进入与退出

学习时可以临时将依赖替换为：

```python
async def get_database():
    print("1. 开始执行依赖")
    async with AsyncSessionLocal() as session:
        print("2. 进入会话上下文")
        try:
            print("3. 即将 yield，会话交给路由")
            yield session
            print("5. 路由已返回，准备提交")
            await session.commit()
        except Exception:
            print("异常分支：回滚并继续抛出")
            await session.rollback()
            raise
        finally:
            print("6. 即将退出会话上下文")
    print("7. 会话上下文已经退出")
```

在路由开头加上：

```python
print("4. 路由正在使用 db")
```

正常请求的打印顺序是 `1 → 2 → 3 → 4 → 5 → 6 → 7`。这里的 `finally` 只用于打印，真正的关闭仍发生在离开 `async with` 时。

如果路由抛出未处理异常，会打印 `1 → 2 → 3 → 4 → 异常分支 → 6`，然后关闭会话并向外传播异常，不会执行普通路径上的 `5` 和 `7`。

## 四、为什么 get_database 不加 @asynccontextmanager

有两层不同的管理：

- SQLAlchemy 的 `AsyncSession` 自带异步上下文管理协议，负责会话进入和退出。
- FastAPI 识别依赖函数中的 `yield`，在内部将依赖适配成上下文管理器，负责在路由执行前后推进它。

所以作为 `Depends` 的依赖，直接写含 `yield` 的 `get_database` 即可，**不需要给它手动添加 `@asynccontextmanager`**。

第 16 节的 `lifespan` 则是通过 `FastAPI(lifespan=lifespan)` 注册，要求传入的函数能创建异步上下文管理器，因此那个例子显式使用了装饰器。两者的注册方式不同。[FastAPI 的 yield 依赖说明](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#context-managers)。

## 五、yield 后的代码到底何时执行

当前项目使用 FastAPI 0.141.1。对于含 `yield` 的依赖：

- `Depends(get_database)`：默认 `scope="request"`，退出代码通常在响应发送后执行。
- `Depends(get_database, scope="function")`：退出代码在路由返回后、响应发送前执行。

原笔记把 `commit()` 放在 `yield` 后面，同时使用默认作用域，可能出现“响应已经发送成功，提交才失败”的情况。因此本篇显式指定 `scope="function"`，让提交异常能在响应发送前交给异常处理逻辑。[FastAPI 关于 scope 的说明](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#early-exit-and-scope)。

这也意味着：路由返回后，会话已经退出，响应内容不应再依赖未加载的 ORM 关系或流式读取。本例查询的是已加载的普通书籍字段。

## 六、另一种写法：让事务上下文管理提交与回滚

如果采用统一的“成功提交、失败回滚”方式，也可以写成：

```python
async def get_database():
    async with AsyncSessionLocal.begin() as session:
        yield session
```

区别是：

- `AsyncSessionLocal()`：创建会话，使用 `async with` 自动关闭；提交要自行决定。
- `AsyncSessionLocal.begin()`：提供一个包含新会话和事务的上下文，正常退出时提交，异常退出时回滚，最后关闭会话。

使用后一种写法时，无需再重复写提交、回滚和关闭；如果希望提交发生在响应前，路由仍使用 `Depends(get_database, scope="function")`。

工厂可以在模块中创建并复用，但不同请求通常创建各自的会话；并发任务也应各自使用会话，避免同时操作同一个 `AsyncSession`。
