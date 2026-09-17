# 36 · FastAPI 项目：全局异常处理器

全局异常处理器把请求执行过程中向外传播的异常，转换成约定格式的 HTTP 响应。本篇按“定义与注册 → 执行过程 → 匹配顺序 → 响应状态码 → 错误详情 → 业务实践”的顺序，整理本次提问及解答。

内容依据当前项目代码，并核对了项目环境中的 Starlette 异常匹配实现。代码片段中的改进方案仅用于说明，与当前实现分别标注。

前置笔记：[35 · 封装通用成功响应格式](../35-FastAPI项目-封装通用成功响应格式/35-FastAPI项目-封装通用成功响应格式.md)。

## 一、实现全局异常处理器的代码原理是什么？

### 1.1 第一步：定义处理函数

[utils/exception.py](../../toutiao_backend/utils/exception.py) 定义了四个异步函数：

| 函数 | 准备处理的异常 | 当前返回方式 |
| --- | --- | --- |
| `http_exception_handler` | `HTTPException` | 使用异常自带的状态码和 `detail` |
| `integrity_error_handler` | `IntegrityError` | 根据约束错误内容选择提示，返回 HTTP 400 |
| `sqlalchemy_exception_handler` | 其他未被更具体处理器处理的 `SQLAlchemyError` | 返回“数据库操作失败，请稍后重试”和 HTTP 500 |
| `generate_exception_handler` | 其余未处理的普通异常 | 返回“服务器内部错误，请稍后重试”和 HTTP 500 |

例如，当前 HTTP 异常处理器的核心代码是：

```python
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        content={
            "code": exc.status_code,
            "message": exc.detail,
            "data": None,
        },
        status_code=exc.status_code,
    )
```

`request` 是当前请求对象，可以读取请求 URL 等信息；`exc` 是本次实际抛出的异常对象。处理器根据它们构造 `JSONResponse`，交给框架发送。

**定义函数本身不会让它自动成为全局异常处理器。**函数名以及 `exc: HTTPException` 这样的类型注解，也不会自动建立异常与处理器的关联。

### 1.2 第二步：注册异常类型与处理函数的对应关系

[utils/exception_handlers.py](../../toutiao_backend/utils/exception_handlers.py) 中注册了：

```python
def register_exception_handlers(app: FastAPI):
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(Exception, generate_exception_handler)
```

以这一行为例：

```python
app.add_exception_handler(IntegrityError, integrity_error_handler)
```

第一个参数是异常类，第二个参数是处理函数对象。这里没有写 `integrity_error_handler()`，因此注册时不会执行函数，而是保存对应关系，等发生异常时再调用。

[main.py](../../toutiao_backend/main.py) 创建应用后执行：

```python
app = FastAPI()
register_exception_handlers(app)
```

注册关联的是这个 `app`。后续这个应用处理请求时，框架才会使用这些配置。

### 1.3 谁捕获异常，谁调用处理器？

FastAPI 底层使用 Starlette 的异常处理机制。对路由或依赖中向外传播的异常，内部的 `ExceptionMiddleware` 按已注册规则选择具体处理器；未处理的异常继续向外传播，由外层 `ServerErrorMiddleware` 使用 `Exception` 对应的兜底处理器。[Starlette：异常处理](https://starlette.dev/exceptions/)

以当前注册用户接口为例：

```text
注册接口调用 create_user()
    ↓
db.add(user)：将对象加入会话
    ↓
await db.flush()：执行 INSERT，违反用户名唯一约束
    ↓
SQLAlchemy 抛出 IntegrityError
    ↓
异常向外传播，get_db() 回滚事务后重新抛出
    ↓
框架匹配到 integrity_error_handler
    ↓
处理器返回 JSONResponse，框架发送错误响应
```

[crud/users.py](../../toutiao_backend/crud/users.py) 中的 `flush()` 执行数据库写入，因此完整性异常可能在这里发生，不必等到 `commit()`。

### 1.4 get_db() 已经捕获异常，为什么全局处理器还能收到？

[config/db_conf.py](../../toutiao_backend/config/db_conf.py) 中的依赖包含：

```python
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

`except` 捕获异常后先回滚，再通过不带参数的 `raise` 重新抛出当前异常，因此外层框架仍然能收到它。

| 所在位置 | 职责 |
| --- | --- |
| 数据库依赖或事务管理代码 | 提交、回滚和释放资源 |
| 全局异常处理器 | 把异常转换成对外响应 |

如果内部代码捕获异常后不再抛出，全局处理器就不会收到被吞掉的异常。返回错误响应后，也不会回到出错语句的下一行继续注册流程。

当前 [routers/users.py](../../toutiao_backend/routers/users.py) 使用 `Depends(get_db, scope="function")`，使依赖退出时的提交发生在响应发送前。这样，即使 `commit()` 才失败，也还有机会返回错误响应；响应已经发出后，异常处理器无法再替换它。

## 二、注册全局异常处理器时，异常如何匹配？顺序怎样？

### 2.1 按注册顺序，还是按继承关系？

**按异常的实际类型及其 MRO 查找，先找自身类型，再沿父类查找；不同父子类型的注册先后不决定匹配优先级。**

当前 Starlette 中负责按类型查找的核心实现是：

```python
for cls in type(exc).__mro__:
    if cls in exc_handlers:
        return exc_handlers[cls]
return None
```

`type(exc)` 获取实际异常类型；`__mro__` 是 Python 规定的类查找顺序。这里可以理解为从具体类型逐步查到父类；多重继承时，以 Python 计算出的 MRO 为准。

找到已注册的类型后立即返回对应处理器，不会继续执行其他处理器。匹配依据也不包括函数名、参数注解或 `str(exc)` 的文字内容。

项目注册函数中的“子类在前，父类在后”注释可以作为排版习惯理解，**不能理解为框架依赖这种注册顺序**。这与普通 `try/except` 按 `except` 分支书写顺序匹配的规则不同。

### 2.2 例子一：抛出 IntegrityError

它相关的继承关系是：

```text
IntegrityError
    ↓
DatabaseError
    ↓
DBAPIError
    ↓
StatementError
    ↓
SQLAlchemyError
```

当前注册了 `IntegrityError`，所以第一步就找到 `integrity_error_handler`。虽然它也是 `SQLAlchemyError` 的子类，但不会再调用父类处理器。

以下两种注册顺序的匹配结果相同：

```python
# 顺序 A：先注册父类，再注册子类
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)

# 顺序 B：先注册子类，再注册父类
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
```

如果没有注册 `IntegrityError`，而中间的几个父类也没有注册，则会继续向上找到 `SQLAlchemyError`，调用 `sqlalchemy_exception_handler`。按当前函数实现，这时会返回通用数据库错误提示和 HTTP 500。

### 2.3 例子二：抛出 OperationalError

假设一次数据库操作抛出 `OperationalError`，它相关的继承关系是：

```text
OperationalError → DatabaseError → DBAPIError → StatementError → SQLAlchemyError
```

项目没有为前面几个类型注册处理器，因此最终选择 `sqlalchemy_exception_handler`。

它不会进入 `integrity_error_handler`，因为 `OperationalError` 不是 `IntegrityError` 的子类。

### 2.4 例子三：抛出 ValueError

假设路由直接执行：

```python
number = int("abc")
```

这会抛出 `ValueError`。项目没有为它注册具体处理器，它也不属于已注册的 HTTP 或 SQLAlchemy 异常类型，因此继续向外传播，最终使用 `generate_exception_handler` 返回 HTTP 500。

`Exception` 是特殊的兜底注册项，会被交给外层的 `ServerErrorMiddleware`，而不是与其他类型一起放进内部的查找表。当前 `app = FastAPI()` 未启用框架调试模式，适用这一兜底流程。

### 2.5 HTTPException 有没有特殊匹配规则？

有。对于 `HTTPException`，框架先查找对应 HTTP 状态码的专用处理器，没有找到时，再按异常类型的 MRO 查找。

例如，假设已经定义以下处理函数：

```python
app.add_exception_handler(404, not_found_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
```

当业务代码抛出：

```python
raise HTTPException(status_code=404, detail="新闻不存在")
```

会优先使用 `not_found_handler`。没有注册 `404` 时，才查找异常类对应的处理器。

数字 `500` 是特殊注册项，与 `Exception` 一样用于配置外层服务器错误处理器，不能简单套用普通状态码的匹配规则。当前项目只注册了 `Exception` 作为兜底。

### 2.6 同一种异常重复注册，顺序有影响吗？

有。注册本质上会更新同一个映射键，后一次覆盖前一次：

```python
app.add_exception_handler(IntegrityError, handler_a)
app.add_exception_handler(IntegrityError, handler_b)
```

最终使用 `handler_b`。这与“父类、子类谁先注册”是两个不同问题。

如果同时注册特殊兜底键 `500` 和 `Exception`，当前 Starlette 构建中间件时也只会选出一个服务器错误处理器；项目中使用一种兜底注册方式即可。

## 三、code 写 exc.status_code、状态码常量、数字有什么区别？

### 3.1 先分清 JSON 的 code 和 HTTP 的 status_code

```python
return JSONResponse(
    content={"code": 400, "message": "数据约束冲突", "data": None},
    status_code=400,
)
```

| 位置 | 含义 |
| --- | --- |
| `content["code"]` | 项目约定的响应体字段，属于普通 JSON 数据 |
| `JSONResponse(status_code=...)` | 真正的 HTTP 响应状态码 |

修改 JSON 中的 `code` 不会自动改变 HTTP 状态码；两者数值也不必相同。例如上一章的成功响应函数使用业务码 `0`，HTTP 状态码仍是 `200`。

### 3.2 三种写法如何选择？可以直接写 500 吗？

| 写法 | 值从哪里来 | 适合表达什么 |
| --- | --- | --- |
| `exc.status_code` | 当前异常对象的属性 | 保留这次 HTTP 异常携带的状态码，可能是 400、401、404 等 |
| `status.HTTP_400_BAD_REQUEST` | 框架提供的整数常量，值为 `400` | 固定使用 HTTP 400，并通过名称表达语义 |
| `400` | 直接写整数 | 固定使用 HTTP 400 |

```python
status.HTTP_400_BAD_REQUEST == 400             # True
status.HTTP_500_INTERNAL_SERVER_ERROR == 500  # True
```

因此，`status_code=status.HTTP_500_INTERNAL_SERVER_ERROR` 可以直接写成 `status_code=500`，运行效果相同。使用常量主要是为了让代码含义更清楚。

### 3.3 为什么 HTTPException 读取状态码，IntegrityError 却固定写 400？

`HTTPException` 本来就用于表达 HTTP 层面的失败，创建它时已经指定了状态码：

```python
raise HTTPException(status_code=404, detail="新闻不存在")
```

处理器读取 `exc.status_code`，就能保留调用方选择的 404。

`IntegrityError` 表示数据库约束错误，不自带 HTTP 状态码。当前代码选择统一转换成 400，这是应用自己的设计，不是 SQLAlchemy 或 FastAPI 强制要求的。实际业务可以根据原因选择响应，例如把明确的唯一值冲突表示为 HTTP 409；无法识别的内部错误则需要单独判断。

## 四、错误的 str 是什么？str(exc) 和 str(exc.orig) 有什么区别？

### 4.1 str(exc) 是把异常对象转换成文字描述

异常是对象，`str(exc)` 通过对象的字符串表示协议获得文字。这里的 `str` 是 Python 内置的字符串类型及转换入口，不是异常对象上一个叫 `str` 的属性。

```python
try:
    int("abc")
except ValueError as exc:
    print(type(exc).__name__)
    print(str(exc))
```

输出：

```text
ValueError
invalid literal for int() with base 10: 'abc'
```

第一行是异常类型名称，第二行是异常的文字描述。具体文字由异常类的 `__str__()` 实现决定；`str(exc)` 本身不提供函数调用堆栈。[Python：内置异常](https://docs.python.org/3.11/library/exceptions.html#BaseException)

相关基础：[对象的字符串表示与特殊方法](../00-python基础补充/11-对象的字符串表示与特殊方法.md)。

### 4.2 exc.orig 是什么？

在 SQLAlchemy 包装底层数据库驱动错误时：

```text
exc       → SQLAlchemy 的异常对象，例如 sqlalchemy.exc.IntegrityError
exc.orig  → 底层驱动的原始异常对象，例如 sqlite3.IntegrityError
```

`orig` 是这类 SQLAlchemy 异常提供的属性，不是所有 Python 异常都具有的属性。例如，不能给普通的 `ValueError` 直接套用 `exc.orig`。[SQLAlchemy：StatementError.orig](https://docs.sqlalchemy.org/en/20/core/exceptions.html#sqlalchemy.exc.StatementError.orig)

SQLite 插入重复用户名时，`str(exc.orig)` 可能是：

```text
UNIQUE constraint failed: user.username
```

同一次错误的 `str(exc)` 通常还包含 SQLAlchemy 添加的上下文。以下使用演示 SQL 和参数：

```text
(sqlite3.IntegrityError) UNIQUE constraint failed: user.username
[SQL: INSERT INTO user (username) VALUES (?)]
[parameters: ('alice',)]
(Background on this error at: https://sqlalche.me/e/20/gkpj)
```

它说明哪条 SQL、哪些参数与错误有关，但依然不等于 Python 的调用堆栈。

项目中的：

```python
error_msg = str(exc.orig)
```

就是取底层数据库的错误描述，再检查里面是否含有特定文字。数据库及驱动不同，这段文字的格式也可能不同。

## 五、traceback.format_exc() 是什么？请举例说明

### 5.1 它返回当前异常的堆栈文本

下面是一个可独立运行的例子：

```python
import traceback

def divide(a, b):
    return a / b

try:
    divide(10, 0)
except Exception as exc:
    print(type(exc).__name__)
    print(str(exc))
    print(traceback.format_exc())
```

前两次打印分别得到：

```text
ZeroDivisionError
division by zero
```

第三次打印的结果类似下面这样，文件名和行号随保存位置变化：

```text
Traceback (most recent call last):
  File "demo.py", line 7, in <module>
    divide(10, 0)
  File "demo.py", line 4, in divide
    return a / b
ZeroDivisionError: division by zero
```

可以从上往下读：第 7 行调用 `divide()`，进入函数后在第 4 行执行除法，最终因为除数为零抛出 `ZeroDivisionError`。

`traceback.format_exc()` 返回一个含换行符的字符串，包含调用路径、文件名、行号和异常描述；它本身不会打印或写日志。示例之所以显示在终端，是因为外面调用了 `print()`。[Python：traceback.format_exc](https://docs.python.org/3.11/library/traceback.html#traceback.format_exc)

### 5.2 为什么没有传入 exc，也能得到异常信息？

它读取的是 Python 当前正在处理的异常，所以通常在 `except` 内调用。即使保存了一个变量 `exc`，也不代表以后任意位置调用 `format_exc()` 都会读取那个变量。

当前项目的异步处理器由框架在捕获异常后调用，仍处于该异常的处理上下文中，因此可以使用它。

如果当前没有正在处理的异常，调用结果通常是字符串：

```python
"NoneType: None\n"
```

如果想明确格式化手里的异常对象，可以使用本项目 Python 版本支持的写法：

```python
error_traceback = "".join(traceback.format_exception(exc))
```

`format_exception(exc)` 返回字符串列表，`"".join(...)` 将它们拼成一个字符串。这里使用的是传入异常对象关联的堆栈；一个仅被构造、从未抛出的异常对象可能没有调用堆栈。

### 5.3 项目里的 error_type、error_detail、traceback 各自回答什么？

```python
error_data = {
    "error_type": type(exc).__name__,
    "error_detail": str(exc),
    "path": str(request.url),
    "traceback": traceback.format_exc(),
}
```

| 字段 | 回答的问题 |
| --- | --- |
| `error_type` | 发生了哪一类异常？ |
| `error_detail` | 这次异常具体描述了什么？ |
| `path` | 哪个请求 URL 触发了错误？ |
| `traceback` | 异常经过哪些函数调用，在哪个文件、哪一行发生？ |

当前 `integrity_error_handler` 的详情使用 `str(exc.orig)`，没有添加 `traceback`；`sqlalchemy_exception_handler` 和 `generate_exception_handler` 则使用 `str(exc)`，并添加堆栈。

## 六、实际业务会像 integrity_error_handler 一样枚举错误吗？

### 6.1 会映射已知错误，但不必穷举所有数据库报错

把有限、明确的失败原因转换成业务提示很常见，例如：

| 已确认的错误原因 | 对用户的提示 |
| --- | --- |
| 用户名唯一约束冲突 | 用户名已存在 |
| 手机号唯一约束冲突 | 手机号已被使用 |
| 删除的数据仍被其他记录引用 | 该数据仍被引用，暂时无法删除 |

但全局处理器不一定掌握每个业务操作的上下文。如果把所有表、所有操作都写成越来越长的字符串 `if/elif`，判断和维护都会变得困难。

还要区分两个阶段：框架先按异常类型选择 `integrity_error_handler`；进入该函数后，才执行里面的字符串判断，决定本次返回什么提示。

### 6.2 当前实现有哪些具体局限？

当前代码是：

```python
error_msg = str(exc.orig)

if "username_UNIQUE" in error_msg or "Duplicate entry" in error_msg:
    detail = "用户名已存在"
elif "FOREIGN KEY" in error_msg:
    detail = "关联数据不存在"
else:
    detail = "数据约束冲突，请检查输入"
```

第一，`Duplicate entry` 不能说明重复的就是用户名。MySQL 中手机号、令牌等唯一值重复，也可能包含这段文字，全局返回“用户名已存在”会误导用户。

第二，当前 [数据库配置](../../toutiao_backend/config/db_conf.py) 使用 SQLite，用户名重复的典型报错是：

```text
UNIQUE constraint failed: user.username
```

它不包含 `username_UNIQUE` 或 `Duplicate entry`。本次用内存 SQLite 复现重复值，并调用现有处理器验证后，返回的提示是“数据约束冲突，请检查输入”，没有命中“用户名已存在”。

第三，外键冲突也可能是删除仍被引用的记录，而不只是插入时“关联数据不存在”。只看 `FOREIGN KEY`，不足以确定业务含义。

数据库错误类别说明违反了什么约束；要返回准确业务提示，还需要知道具体约束和当前操作。

### 6.3 业务中怎样划分处理职责？

可以按下面的方式组织。这是设计建议，不是当前代码已经全部实现的功能：

| 层次 | 负责的事情 |
| --- | --- |
| 业务层 | 判断用户名已存在等可预期失败，抛出明确的业务异常 |
| 数据访问层或业务操作边界 | 识别已知数据库错误，结合约束和操作转换成业务异常 |
| 事务管理代码 | 按事务边界回滚，继续传播需要对外处理的异常 |
| 全局异常处理器 | 统一状态码和响应格式，对未知错误兜底 |

小项目可以直接抛出 `HTTPException`。业务增多后，也可以定义 `UsernameAlreadyExists` 等业务异常，再注册相应处理器，避免业务代码到处重复组织 HTTP 响应。

识别底层数据库错误时，优先考虑驱动提供的结构化错误码、SQLSTATE、约束名等信息；这些信息是否可用、字段叫什么，取决于数据库和驱动，没有所有数据库通用的一套属性。必须解析报错文本时，可以把这部分逻辑集中封装，并保留无法识别时的处理路径。

明确的唯一值冲突可以采用 HTTP 409 等符合接口约定的响应。未识别的 `IntegrityError` 不一定是用户输入错误，也可能是程序漏填必需字段，因此不应不加区分地认定为用户的 400 错误。

### 6.4 已经提前查询用户名，为什么还需要处理数据库异常？

因为先查再写之间存在并发窗口：

```text
请求 A：查询 alice，不存在
请求 B：查询 alice，不存在
请求 A：插入并提交 alice，成功
请求 B：插入 alice，违反唯一约束
```

提前查询能更早给出业务提示，但最终仍要由数据库唯一约束保证数据不重复，并处理写入时发生的冲突。

当前注册接口保留了查询 `existing_user` 的代码，但“存在就抛出 HTTPException”的分支被注释掉了，因此查询结果目前不会阻止后续创建用户。数据库唯一约束仍然承担最终检查。

## 七、当前实现还需要区分哪些边界？

### 7.1 注册 Exception 后，所有错误都会变成统一格式吗？

不会。已经被更具体的处理器处理的异常，不会继续进入兜底函数。FastAPI 默认就有一些处理器，例如请求参数校验的 `RequestValidationError`；它通常返回默认格式的 HTTP 422。

此外，项目注册的是 FastAPI 的 `HTTPException`，它是 Starlette `HTTPException` 的子类。框架产生的路由 404 等可能直接使用 Starlette 的基类异常，不能反向匹配到子类处理器。若要覆盖这些情况，需要考虑注册 Starlette 的 `HTTPException`，并单独统一请求校验异常。[FastAPI：错误处理](https://fastapi.tiangolo.com/tutorial/handling-errors/)

“全局”指应用请求处理范围内的统一规则，并不表示任意后台任务、启动过程或其他进程中的错误都能转换成当前请求的响应。响应已经发送后，再发生异常也无法改写已发送的内容。

### 7.2 DEBUG_MODE 和 traceback 会自动记录日志吗？

不会。当前 `DEBUG_MODE = True` 只是项目自定义变量，控制是否把错误详情和部分堆栈放进响应的 `data` 字段。构造这些字符串并返回 JSON，不等于主动写入服务端日志。

业务部署时通常把诊断详情留在服务端日志中，对外返回可理解的提示，避免把 SQL 参数、请求信息和堆栈直接暴露给客户端。

这个变量与 `FastAPI(debug=True)` 独立。框架自己的 `debug=True` 会影响未处理服务器错误的响应方式：使用调试堆栈响应，而不是自定义的 500 兜底响应。当前项目使用 `FastAPI()`，没有打开这个框架调试选项。[Starlette：调试模式与异常响应](https://starlette.dev/exceptions/)
