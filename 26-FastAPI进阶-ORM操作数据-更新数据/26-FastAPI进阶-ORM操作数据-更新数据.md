# 26-FastAPI进阶-ORM操作数据-更新数据

核心操作：**查询 `get()` → 给 ORM 对象的属性重新赋值 → `commit()` 提交到数据库。**

本节沿用根目录 [database_sqlite.py](../database_sqlite.py) 的 `Book` 模型、SQLite 数据库和异步会话，使用 **SQLAlchemy 2.x + Pydantic 2.x**。先掌握单条更新，再学习部分更新、条件更新和批量更新。

需要先分清两件事：**SQLAlchemy 决定“如何修改数据库”，HTTP 的 PUT、PATCH 决定“接口向客户端表达什么操作”。** 数据库执行 `UPDATE`，并不意味着接口必须使用 PUT。

## 一、更新数据的基本原理

```python
# 放在异步函数内；db 是 AsyncSession
book = await db.get(Book, 1)
if book is not None:
    book.price = 49.0
    await db.commit()
```

这里的 `book` 是当前会话管理的 ORM 对象。给 `book.price` 赋值后，会话会跟踪属性变化，在 `flush()` 时生成 `UPDATE`，`commit()` 会先自动执行必要的 `flush()`，再提交事务。

```text
await db.get(Book, book_id)  按主键获取对象，不存在时返回 None
    ↓
book.price = 49.0           修改 Python 对象，会话跟踪变化
    ↓
flush                      将变化写入当前数据库事务
    ↓
commit                     提交事务，保存修改
```

注意：

- `get(Book, book_id)` 按**主键**获取；按书名、作者等条件获取仍用 `select(...).where(...)`。
- `get()` 会先检查会话中是否已有可用对象，因此不一定每次都执行 `SELECT`。
- 从同一会话查询出来的对象已经受会话管理，**修改后不需要再 `db.add(book)`**。
- `book.price = 49.0` 本身不是异步操作，不写 `await`。
- 自动 `flush` 也可能发生在后续 ORM 查询前，不能认为 SQL 一定只在 `commit()` 那一行执行。
- 对于这里已经加载的普通标量属性，重复赋相同值通常不会产生有效修改，也不一定发出 `UPDATE`。

这种方式称为 ORM 的工作单元更新：由会话收集对象变化并写入数据库。[SQLAlchemy 对象更新](https://docs.sqlalchemy.org/en/20/tutorial/orm_data_manipulation.html#updating-orm-objects-using-the-unit-of-work-pattern)

## 二、示例准备：模型、依赖和事务分工

### 1. 复用哪些代码

下面的代码块是学习示例，可放在根目录 `database_sqlite.py` 的模型、`app`、`AsyncSessionLocal` 定义之后。`Book` 的四个业务字段是：

```text
bookname：书名，字符串，数据库不允许 NULL
author：作者，字符串，数据库不允许 NULL
price：价格，浮点数，数据库不允许 NULL
publisher：出版社，字符串，数据库不允许 NULL
```

本节增加独立的 `BookPut`、`BookPatch` 和 `get_update_database`，便于与现有课堂代码对照。PUT 示例继续使用原路径，实际接入时应**替换原来的同路径 PUT 路由**，不要重复注册。其余更新方式是独立函数，按需选用。

公共导入和响应模型：

```python
from datetime import datetime

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession


class BookPut(BaseModel):
    # 只接收允许编辑的字段，拼错字段名、传入 id 等都会报 422
    model_config = ConfigDict(extra="forbid")

    bookname: str = Field(min_length=1, max_length=255)
    author: str = Field(min_length=1, max_length=255)
    price: float = Field(ge=0, allow_inf_nan=False)
    publisher: str = Field(min_length=1, max_length=255)


class BookRead(BookPut):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    create_time: datetime
    update_time: datetime
```

`BookPut` 是 Pydantic 请求模型，用于校验输入；`Book` 是 ORM 模型，用于操作数据库。`BookRead` 通过 `from_attributes=True` 从 ORM 对象属性读取响应字段。

这里的非负价格、非空字符串是本节接口增加的校验规则；它们不会自动给现有数据库增加约束。`min_length=1` 也不等于禁止纯空格字符串，如有需要可进一步增加去空格校验。

### 2. 路由负责提交，依赖负责回滚和关闭

```python
async def get_update_database():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

本节路由在成功返回前调用 `commit()`；发生异常时，依赖回滚当前未提交的事务，退出 `async with` 时自动关闭会话。

当前根目录的 `get_database()` 在 `yield` 后还会提交，原更新路由也提交了一次。本节用新的依赖明确事务分工，避免重复负责提交。独立的更新函数则在函数内处理提交失败和回滚。

## 三、方式一：查询对象后逐个赋值（单条更新首选）

### 1. 完整 PUT 接口

```python
@app.put("/book/update_book/{book_id}", response_model=BookRead)
async def replace_book(
    book_id: int,
    data: BookPut,
    db: AsyncSession = Depends(get_update_database),
):
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    book.bookname = data.bookname
    book.author = data.author
    book.price = data.price
    book.publisher = data.publisher

    await db.commit()
    await db.refresh(book)
    return book
```

这里将 PUT 定义为：**完整设置一本书允许客户端编辑的四个业务字段**。四个字段都必须提交，漏传时 FastAPI 返回 `422`；主键、创建时间、更新时间由服务器管理，不要求客户端提供。

请求示例：

```http
PUT /book/update_book/1
Content-Type: application/json

{
  "bookname": "FastAPI数据库实践",
  "author": "张三",
  "price": 49.0,
  "publisher": "学习出版社"
}
```

**适用场景：**编辑单条记录；修改前需要确认存在、检查旧值或执行业务判断。

### 2. commit() 和 refresh() 的区别

| 方法 | 作用 | 是否提交事务 | 返回值 |
| --- | --- | --- | --- |
| `await db.flush()` | 将会话里待处理的变化发送给数据库 | 否 | `None` |
| `await db.commit()` | 先自动 flush，再提交事务 | 是 | `None` |
| `await db.refresh(book)` | 查询数据库，重新加载对象属性 | 否 | `None` |
| `await db.rollback()` | 回滚当前尚未提交的事务 | 否 | `None` |

不要写 `book = await db.commit()` 或 `book = await db.refresh(book)`，否则会把变量覆盖成 `None`。

本项目的 `update_time` 使用 `onupdate=func.now()`。更新后它的最新值可能需要额外查询，所以返回包含时间字段的对象前，显式 `refresh(book)` 更清楚。虽然配置了 `expire_on_commit=False`，它也只是不在提交时统一使属性过期，**不保证数据库生成的字段都已加载**。异步环境下，直接读取未加载或过期属性可能触发隐式数据库访问，导致 `MissingGreenlet` 等错误。[异步会话与隐式 IO](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#preventing-implicit-io-when-using-asyncsession)

`refresh()` 是读取，不是保存。这里它发生在提交之后；如果读取或响应构造失败，已经提交的修改也不会被后续 `rollback()` 撤销。

## 四、方式一的常见变体：setattr() + PATCH 部分更新

编辑页面可能只修改价格，不想重新发送书名、作者和出版社。这时可以使用 PATCH，只处理请求中实际出现的字段。

### 1. 所有字段允许省略，但本表不接受显式 null

```python
class BookPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bookname: str | None = Field(default=None, min_length=1, max_length=255)
    author: str | None = Field(default=None, min_length=1, max_length=255)
    price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    publisher: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("bookname", "author", "price", "publisher")
    @classmethod
    def reject_explicit_null(cls, value: str | float | None) -> str | float:
        if value is None:
            raise ValueError("该字段可以省略，但不能设置为 null")
        return value
```

这里要区分“可以不传”和“可以保存为 NULL”：

- `default=None` 让字段可以省略。
- `str | None` 这类类型注解本身也允许显式传 `null`，因此本例额外使用校验器拒绝它。
- 默认配置下，省略字段时不校验默认值；显式传入 `null` 时会进入校验器并返回 `422`。
- 这样能配合当前 `Book` 的非空列，避免把 `None` 写进数据库后才触发约束异常。

### 2. 完整 PATCH 接口

```python
@app.patch("/book/update_book/{book_id}", response_model=BookRead)
async def patch_book(
    book_id: int,
    data: BookPatch,
    db: AsyncSession = Depends(get_update_database),
):
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="请至少提供一个要更新的字段")

    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    for field, value in changes.items():
        setattr(book, field, value)

    await db.commit()
    await db.refresh(book)
    return book
```

请求只包含价格：

```http
PATCH /book/update_book/1
Content-Type: application/json

{"price": 0}
```

结果是价格变为 `0`，其他业务字段保持原值。空对象 `{}` 返回 `400` 是本示例的接口约定，不是 PATCH 协议强制要求。

`setattr(book, "price", 0)` 等价于 `book.price = 0`。它只是动态属性赋值，**与逐个赋值属于同一种 ORM 更新机制**，不会额外创建一条记录。

这里遍历的是经过校验、只包含允许编辑字段的模型数据。不要把未经筛选的任意请求字典直接用于 `setattr()` 或 `.values(**data)`，否则可能允许修改主键等不应开放的字段。

### 3. exclude_unset、exclude_none、exclude_defaults 的区别

```python
data = BookPatch(price=0)

print(data.model_dump())
# {'bookname': None, 'author': None, 'price': 0.0, 'publisher': None}

print(data.model_dump(exclude_unset=True))
# {'price': 0.0}
```

| 参数 | 排除什么 | 对部分更新的影响 |
| --- | --- | --- |
| `exclude_unset=True` | 创建模型时没有显式提供的字段 | 能识别“客户端没有传”，通常用于 PATCH |
| `exclude_none=True` | 值为 `None` 的字段 | 会把客户端明确传入的 `null` 也排除 |
| `exclude_defaults=True` | 值与默认值相同的字段 | 可能排除客户端明确要设置的默认值 |

假如以后某列允许 NULL，客户端传 `{"publisher": null}` 可能表示“清空出版社”；这时应允许该字段的 `None`，并用 `exclude_unset=True` 保留这个明确操作。当前模型和表不支持清空，所以本例拒绝 `null`。[Pydantic 字段排除规则](https://docs.pydantic.dev/latest/concepts/serialization/#excluding-and-including-fields-based-on-their-value)

不能用 `if value:` 判断是否传了字段，因为 `0`、`False`、`""` 都是假值。**有没有传，看字段是否出现；值是否合法，由校验规则判断。**

## 五、方式二：execute(update(...)) 按条件直接更新

这种方式不需要先加载每个 `Book` 对象，而是直接构造 SQL `UPDATE`。

### 1. 按 ID 更新一条记录

```python
async def update_price_by_id(db: AsyncSession, book_id: int, new_price: float):
    stmt = (
        update(Book)
        .where(Book.id == book_id)
        .values(price=new_price)
    )

    try:
        result = await db.execute(stmt)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Book not found")
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"matched_count": result.rowcount}
```

参数值应先由调用方校验，例如使用 `BookPut` 或 `BookPatch` 的价格约束。这个函数本身不是 FastAPI 路由，类型注解不会自动提供请求校验。

逐步理解：

1. `update(Book)`：指定更新书籍表。
2. `.where(Book.id == book_id)`：指定目标记录。
3. `.values(price=new_price)`：指定要修改的字段和值。
4. `await db.execute(stmt)`：执行 SQL，返回执行结果，**不是 Book 对象**。
5. `await db.commit()`：提交事务；`execute()` 不会自动提交。

生成的 SQL 大致如下，实际占位符和字段顺序取决于数据库方言：

```sql
UPDATE book
SET price = ?, update_time = CURRENT_TIMESTAMP
WHERE book.id = ?;
```

`rowcount` 通常表示 **WHERE 匹配的行数**，不是“价格确实发生变化的行数”。即使新旧价格相同，也可能为 `1`。本项目 SQLite 的普通单条 UPDATE 可以这样检查；部分驱动、`RETURNING` 或批量执行场景可能不提供可靠值，甚至返回 `-1`，不能把该写法无条件照搬。[UPDATE 与 rowcount](https://docs.sqlalchemy.org/en/20/tutorial/data_update.html#getting-affected-row-count-from-update-delete)

### 2. 一个条件更新多行

需求：把“学习出版社”的所有书统一设为 `39` 元。

```python
async def update_publisher_prices(db: AsyncSession):
    stmt = (
        update(Book)
        .where(Book.publisher == "学习出版社")
        .values(price=39.0)
    )
    try:
        result = await db.execute(stmt)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"matched_count": result.rowcount}
```

这个条件可能匹配零行、一行或多行；本例零行返回 `0`，不作为错误。省略 `.where(...)` 则会更新整张表，只有确实需要全表修改时才这样写。

**适用场景：**按状态、出版社、价格区间等条件批量修改；不需要逐个对象执行业务逻辑。相比先查询所有对象再循环赋值，可以减少对象加载和管理开销。

### 3. 使用 SQL 表达式更新

需求：符合条件的书在原价基础上增加 `5` 元。

```python
async def increase_publisher_prices(db: AsyncSession):
    stmt = (
        update(Book)
        .where(Book.publisher == "学习出版社")
        .values(price=Book.price + 5)
    )
    try:
        result = await db.execute(stmt)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"matched_count": result.rowcount}
```

`Book.price + 5` 是交给数据库执行的表达式，对应 `SET price = price + 5`。它避免了先在 Python 读取旧价、再计算并覆盖时的那类并发丢失更新，但不等于解决所有并发问题。

**固定赋值与累加的区别：**反复“设为 39 元”，价格仍是 39；反复“增加 5 元”，价格会持续增加。后者不应直接包装成声称幂等的 PUT 接口。

### 4. 扩展：UPDATE ... RETURNING

支持 `RETURNING` 的数据库可以在执行更新时直接返回指定字段：

```python
async def update_price_returning(db: AsyncSession, book_id: int, new_price: float):
    stmt = (
        update(Book)
        .where(Book.id == book_id)
        .values(price=new_price)
        .returning(Book.id, Book.price, Book.update_time)
    )
    try:
        result = await db.execute(stmt)
        row = result.mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Book not found")
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return dict(row)
```

此处返回字段映射，不是 ORM 对象，也不依赖 `rowcount`。项目当前环境的 SQLite 支持该示例；MySQL 不支持同样的 UPDATE RETURNING 用法，迁移数据库时要检查方言支持。[UPDATE RETURNING](https://docs.sqlalchemy.org/en/20/tutorial/data_update.html#using-returning-with-update-delete)

### 5. 会话中已经加载的对象如何同步

`execute(update(Book)...)` 直接修改数据库时，会话中可能已有同一行的旧对象。针对这种自定义 WHERE 的 ORM 更新，SQLAlchemy 提供 `synchronize_session` 策略：

```python
stmt = (
    update(Book)
    .where(Book.id == 1)
    .values(price=59.0)
    .execution_options(synchronize_session="fetch")
)
# 在异步函数内 await db.execute(stmt)，然后提交
```

- `"auto"`：默认策略，根据后端能力选择同步方式。
- `"fetch"`：通过查询或 RETURNING 确定受影响对象，更新或使相关属性过期。
- `"evaluate"`：尝试在 Python 中判断哪些已加载对象匹配；复杂条件可能不支持。
- `False`：不做对象同步；会话里的旧对象可能仍保留旧值。

不要为了省事到处关闭同步。后续需要读取对象、特别是数据库生成字段时，可以显式 `await db.refresh(book)`。本节一般示例保留默认策略。[会话同步策略](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html#selecting-a-synchronization-strategy)

## 六、方式三：按主键批量更新，每行设置不同值

如果 ID 为 1、2、3 的书要分别设置不同价格，可把字典列表传给 `execute()`：

```python
async def bulk_update_books(db: AsyncSession, changes: list[dict]):
    if not changes:
        return

    try:
        await db.execute(update(Book), changes)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
```

调用示例，假设这些 ID 已经存在：

```python
# 放在异步函数内
await bulk_update_books(
    db,
    [
        {"id": 1, "price": 29.0},
        {"id": 2, "price": 39.0},
        {"id": 3, "price": 49.0, "publisher": "技术出版社"},
    ],
)
```

这是 SQLAlchemy 2.x 的 **ORM Bulk UPDATE by Primary Key**：

- 每个字典必须包含完整主键；本表是 `id`。它用于定位记录，不是要求把主键改成这个值。
- 其他键使用 ORM 属性名，表示这一行要修改的字段；调用方仍需校验字段白名单和值。
- 通常不写 `.values(...)`，每行的新值来自字典；框架自动补上主键 WHERE 条件。
- 使用批量参数执行，不承诺只发出一条 SQL；字段组合不同还可能分组执行。
- 这种模式不支持 UPDATE RETURNING，也不要假定结果一定有可用的 `rowcount`。
- 缺失目标行时，在支持行数检查的驱动上可能抛出 `StaleDataError`。不要把 `len(changes)` 当成已经核实的实际更新行数。

本例只在全部执行成功后提交；异常则回滚这一批未提交修改。[SQLAlchemy 按主键批量更新](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html#orm-bulk-update-by-primary-key)

与上一节的区别：`update(Book).where(...).values(price=39)` 是**符合条件的行应用同一规则**；`execute(update(Book), 字典列表)` 是**每个主键对应自己的字段和值**。

## 七、补充方式：参数化原生 SQL

复杂 SQL、数据库专有功能或已有 SQL 脚本中，也可能直接执行文本语句。这属于 SQL 操作，不走 ORM 对象属性跟踪。

```python
async def update_price_by_sql(db: AsyncSession, book_id: int, new_price: float):
    stmt = text("""
        UPDATE book
        SET price = :price, update_time = CURRENT_TIMESTAMP
        WHERE id = :book_id
    """)
    try:
        result = await db.execute(
            stmt,
            {"price": new_price, "book_id": book_id},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Book not found")
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"matched_count": result.rowcount}
```

`:price`、`:book_id` 是绑定参数，值通过单独的字典传入。不要用 f-string 把客户端输入拼进 SQL；绑定参数用于数据值，不能用来直接替换任意表名、列名。[SQLAlchemy 文本语句与绑定参数](https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.text)

原生文本 SQL 不会自动利用模型里的 `onupdate=func.now()`，所以本例显式更新 `update_time`。它也不会自动同步会话中已经加载的 `Book` 对象，需要时显式刷新。

## 八、阅读旧教程时会遇到的写法

下面两种是**旧式接口示例，使用同步 `Session`**，用来识别历史代码。本项目的 `AsyncSession` 不应直接照抄调用。

### 1. Query.update()

```python
from sqlalchemy.orm import Session


def legacy_query_update(db: Session, book_id: int):
    try:
        matched_count = (
            db.query(Book)
            .filter(Book.id == book_id)
            .update({Book.price: 49.0}, synchronize_session="fetch")
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return matched_count
```

它在 SQLAlchemy 2.x 中仍作为旧式 API 保留，但新代码优先使用 `execute(update(...))`。不要写 `await db.query(...)`，`AsyncSession` 没有这种直接查询接口。[旧式 Query.update](https://docs.sqlalchemy.org/en/20/orm/queryguide/query.html#sqlalchemy.orm.Query.update)

### 2. bulk_update_mappings()

```python
def legacy_bulk_update(db: Session):
    try:
        db.bulk_update_mappings(
            Book,
            [{"id": 1, "price": 29.0}, {"id": 2, "price": 39.0}],
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
```

它是旧式按主键批量更新接口，不提供现代接口的会话同步能力。新代码优先使用第六节的 `await db.execute(update(Book), changes)`。[旧式批量更新](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html#legacy-session-bulk-update-methods)

## 九、为什么更新接口经常使用 PUT

### 1. PUT 表达“把指定资源设置为这份状态”

HTTP 中，PUT 请求客户端指定的目标 URI，并要求用请求中的表示创建或替换该资源的状态。因此，更新已知 ID 的书籍信息，经常使用：

```http
PUT /books/1
Content-Type: application/json

{
  "bookname": "FastAPI数据库实践",
  "author": "张三",
  "price": 49.0,
  "publisher": "学习出版社"
}
```

可以读作：“请把 `/books/1` 的可编辑书籍信息设置成这份内容。”`/books/1` 是常见的资源式路径；课堂的 `/book/update_book/1` 也能工作，路径中写 `update_book` 并不会自动决定 HTTP 方法。

**“完整替换资源状态”不等于删除数据库旧行再插入，也不要求 SQL 更新所有列。** 接口定义客户端能编辑哪些字段，ORM 可以只对发生变化的列执行 UPDATE。[RFC 9110：PUT](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.4)

### 2. PUT 具有幂等语义

幂等是指：**在相同起点、没有其他操作干扰时，相同请求执行一次或多次，预期的资源修改效果相同。**

```text
把价格设为 49 元：
执行一次 → 49
重复执行 → 49          固定赋值，符合幂等语义

把价格增加 5 元，原价为 40 元：
执行一次 → 45
重复执行 → 50          累加操作，不幂等
```

当客户端因网络问题不确定请求是否成功时，幂等设计有利于重试。但幂等不要求每次 HTTP 响应完全一致，也不禁止服务器为每次请求记录日志等附带行为。审计时间变化也不能简单等同于“业务更新不幂等”。[RFC 9110：幂等方法](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)

写上 `@app.put(...)` 只注册路由，**FastAPI 不会自动把内部业务逻辑变得幂等**。如果里面每次执行 `price = price + 5`，就没有遵守 PUT 所表达的语义。

### 3. PUT、PATCH、POST 怎么选

| 方法 | 常见用途 | 本项目中的例子 | 幂等性 |
| --- | --- | --- | --- |
| GET | 读取资源 | 获取一本书 | 应幂等，不能用来请求修改数据 |
| POST | 创建资源，或提交业务动作 | 新增书籍；执行一次调价操作 | 协议不保证，可另行设计去重 |
| PUT | 完整设置指定资源的可编辑状态 | 提交四个业务字段替换书籍信息 | 应幂等 |
| PATCH | 根据请求内容修改资源的部分状态 | 仅提交 `price` | 不保证，但固定赋值可以设计为幂等 |

PATCH 专门表达对资源施加修改；既可以设计为“价格设为 49”，也可以承载“在原价上增加 5”这类操作，所以不能说“所有 PATCH 都不幂等”。本节采用常见的 JSON 字段更新约定，具体省略、空值和校验规则由接口定义；并不是所有 PATCH 接口都接收相同格式的 JSON。[RFC 5789：PATCH](https://www.rfc-editor.org/rfc/rfc5789.html#section-2)

POST 可以用于业务操作，SQL UPDATE 也可以在 POST 路由内执行；GET 的语义是读取，不应设计成修改书籍的接口。[HTTP 方法语义](https://www.rfc-editor.org/rfc/rfc9110.html#section-9)

### 4. 结合当前课堂代码理解

目前根目录的 `BookUpdate` 要求书名、作者、价格必传，但出版社可以省略，更新时还写了：

```python
if data.publisher:
    book.publisher = data.publisher
```

因此，这个 PUT 路由的实际行为是：“前三个字段更新，出版社只有在值为真时更新”。它是课堂里常见的混合写法。

进一步规范时，可以像本笔记这样拆成两个明确接口：

- **PUT + BookPut**：四个业务字段必传，完整设置。
- **PATCH + BookPatch**：字段可省略，只更新实际提交的字段；不合法的空值明确报错。

FastAPI 不强制 PUT 一定完整更新，也允许开发者在 PUT 中写部分更新；但按照方法语义设计，更方便调用者理解和正确重试。[FastAPI 更新请求体教程](https://fastapi.tiangolo.com/tutorial/body-updates/)

### 5. 更新成功和失败返回什么

| 情况 | 常见状态码 | 本节约定 |
| --- | --- | --- |
| 更新成功并返回数据 | `200 OK` | PUT、PATCH 返回更新后的书籍 |
| 更新成功，不返回响应体 | `204 No Content` | 可作为另一种设计，不能再附带 JSON 响应体 |
| 目标记录不存在 | `404 Not Found` | 本节只更新已有书籍 |
| 字段缺失、类型错误或违反模型校验 | `422 Unprocessable Content` | 如 PUT 漏传出版社、PATCH 传负数价格 |
| PATCH 没有提供任何修改字段 | `400 Bad Request` | 本节自行约定 |

PUT 也可以设计为在目标不存在时创建资源，成功创建返回 `201`；协议没有要求每个 PUT 接口都必须支持创建。本节遇到不存在的 ID 返回 `404`，不会自动变成新增操作。[PUT 响应语义](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.4)

## 十、更新操作的常见问题

### 1. 不要把新增对象当成更新

```python
# 反例：不是“按已有 ID 更新”
book = Book(id=1, bookname="新书名", author="张三", price=49, publisher="学习出版社")
db.add(book)
# 后续提交通常会尝试 INSERT；如果主键 1 已存在，会出现冲突
```

常规更新使用“查询现有对象后赋值”，或带 WHERE 的 `update()`。`add()` 不会因为新对象带了已有 ID，就自动改成 UPDATE。

### 2. onupdate 不是数据库触发器

当前 `update_time` 定义中的：

```python
# 模型列配置片段
onupdate=func.now()
```

表示 SQLAlchemy 构造相关 UPDATE、且调用方没有显式指定该列值时，将该表达式放入更新语句。它**不等于在数据库里创建了一个自动更新触发器**。

因此，ORM 属性更新和 `update(Book)` 可以利用这项配置；手写 `text("UPDATE ...")` 则需要自己处理。若对象没有有效变化、没有发出 UPDATE，时间也不会仅因调用 `commit()` 就自动改变。`default` / `insert_default` 用于插入默认值；更新默认值由 `onupdate` 配置。[SQLAlchemy 插入与更新默认值](https://docs.sqlalchemy.org/en/20/core/defaults.html#client-invoked-sql-expressions)

### 3. 事务提交和异常处理要配套

- `flush()`、`execute()` 执行成功，不代表事务已经提交。
- 提交或刷新数据库操作失败后，应回滚未提交的事务，再继续使用会话。
- 一批修改要求一起成功时，放进同一个事务，最后统一提交；不要循环里每条提交一次。
- `commit()` 成功后，`rollback()` 不能撤销那次已提交的修改。
- 如果在已有事务的业务流程里复用本节独立函数，应把提交责任移到外层统一管理，避免函数提前提交外层其他修改。

### 4. 幂等不等于不会发生并发覆盖

两个客户端先后读到同一本书，再各自提交完整 PUT，后提交的请求可能覆盖先提交的修改。PATCH 可以减少无关字段覆盖，但同时修改同一字段仍可能冲突。

进一步可以学习版本号校验，或用 `ETag` + `If-Match` 让服务器拒绝基于旧版本的修改。`If-Match` 条件不满足通常返回 `412 Precondition Failed`。这些是并发控制机制，不是写了 PUT 或调用了 `commit()` 就自动具备的。[If-Match 与防止丢失更新](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.1)

## 十一、方法选择与练习

| 需求 | 优先选择 |
| --- | --- |
| 修改一本书，需要检查它是否存在或读取旧值 | `get()` → 属性赋值 → `commit()` |
| 只修改客户端传来的字段 | PATCH + `exclude_unset=True` + `setattr()` |
| 按条件给很多记录设置相同值或应用同一表达式 | `execute(update(Book).where(...).values(...))` |
| 已知多个主键，每行更新内容不同 | `execute(update(Book), 字典列表)` |
| 需要直接取回更新字段，数据库支持 RETURNING | `update(...).returning(...)` |
| 需要直接执行特定 SQL | 参数化 `text(...)` |
| 阅读旧版同步代码 | 认识 `Query.update()`、`bulk_update_mappings()` |

可以在测试书籍上依次练习；ID 以实际新增返回值为准：

1. 用完整 PUT 修改四个业务字段，再用现有 GET 接口核对。
2. 用相同 PUT 连续请求两次，观察四个业务字段是否一致。
3. 用 PATCH 提交 `{"price": 0}`，确认价格变为零，其他业务字段不变。
4. 分别提交 `{}`、`{"price": -1}`、`{"publisher": null}` 和 `{"id": 99}`，观察校验响应。
5. 修改不存在的 ID，确认单条更新接口返回 `404`。
6. 比较“按出版社统一调价”和“按主键分别调价”的 SQL 日志，理解两种批量更新的区别。

关联复习：[新增数据与事务](../25-FastAPI进阶-ORM操作数据-新增数据/25-FastAPI进阶-ORM操作数据-新增数据.md)、[ORM 对象](../00-python基础补充/08-ORM对象.md)、[SQLAlchemy 查询结果与取值](../00-python基础补充/09-SQLAlchemy查询结果与取值.md)。
