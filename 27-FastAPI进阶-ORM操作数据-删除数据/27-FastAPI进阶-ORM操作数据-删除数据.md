# 27-FastAPI进阶-ORM操作数据-删除数据

核心步骤：**查询 `get()` → 删除 `delete()` → 提交 `commit()` 到数据库。**

本节沿用本目录 [database_sqlite.py](./database_sqlite.py) 中的 `Book`、`app`、`AsyncSessionLocal`，使用 **SQLAlchemy 2.x + SQLite + AsyncSession 异步会话**。先掌握单条删除，再学习条件删除、批量删除和软删除。

先分清两个层次：**数据库删除方式决定数据如何处理，HTTP DELETE 决定接口向客户端表达什么操作。** DELETE 接口可以执行数据库 `DELETE`，也可以通过 `UPDATE` 标记为已删除。

## 一、删除数据的基本原理

```python
# 放在异步函数内；db 是 AsyncSession
book = await db.get(Book, 1)
if book is not None:
    await db.delete(book)
    await db.commit()
```

可以按下面的顺序理解：

```text
await db.get(Book, book_id)  按主键获取 ORM 对象，不存在时返回 None
    ↓
await db.delete(book)       把对象登记为待删除
    ↓
flush                      执行数据库 DELETE，尚未提交事务
    ↓
commit                     提交事务，保存删除结果
```

`commit()` 会先自动执行必要的 `flush()`。会话默认也可能在某些 ORM 查询之前自动 flush，因此 DELETE 不一定只在 `commit()` 那一行执行。[SQLAlchemy 对象删除与 flush](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#deleting)

### 1. 为什么 delete() 要写 await

本项目使用的是 `AsyncSession`：

```python
await db.delete(book)  # 异步会话
```

它可能为了处理关联对象的级联规则，查询尚未加载的关系，所以是异步方法。**能够 await，不等于此时已经提交删除。** 本行主要是登记对象删除，数据库 DELETE 在 flush 时执行。[AsyncSession.delete](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.AsyncSession.delete)

| 写法 | 含义 | 返回值 |
| --- | --- | --- |
| `await db.get(Book, book_id)` | 按主键获取对象 | `Book` 或 `None` |
| `await db.delete(book)` | 将对象登记为待删除 | `None` |
| `await db.flush()` | 把待处理变化写入当前事务 | `None` |
| `await db.commit()` | 提交事务 | `None` |
| `await db.rollback()` | 回滚当前未提交事务 | `None` |

不要写 `book = await db.delete(book)`，也不要把 `commit()` 的返回值当成删除数量。

### 2. delete() 接收的是对象，不是 ID 或模型类

```python
# 正确：先按主键取得实际对象
book = await db.get(Book, book_id)
if book is not None:
    await db.delete(book)

# 错误示意，不要执行：
# await db.delete(book_id)  # 整数不是 ORM 对象
# await db.delete(Book)    # 模型类不是这一行的对象
```

不要临时构造 `Book(id=1)` 就交给 `db.delete()`；这个新对象不是已经持久化的记录。想省略查询时，使用后面的 `delete(Book).where(...)`。

## 二、示例准备：导入和事务分工

公共导入：

```python
from datetime import datetime

from fastapi import Depends, HTTPException, Query, Response
from sqlalchemy import DateTime, delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
```

注意同名操作的区别：

- `db.delete(book)` 是会话方法，接收 **Book 对象**。
- `delete(Book)` 是从 SQLAlchemy 导入的语句构造函数，接收 **Book 模型类**。
- `@app.delete(...)` 是 FastAPI 路由装饰器，注册 **HTTP DELETE 接口**。

本节使用独立依赖，让**路由负责提交，依赖负责异常回滚和关闭会话**：

```python
async def get_delete_database():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

当前课堂代码的 `get_database()` 在 `yield` 后提交一次，删除路由内又提交一次。本节增加这个独立依赖，便于对照，避免重复负责提交。退出 `async with` 会自动关闭会话。

下面的接口代码放在模型、`app`、会话工厂定义之后。第一种写法与原删除路由路径相同，实际接入时应**替换原路由，不能重复注册**；后面的其他写法按需要选用。独立函数不是路由，直接调用时不会自动获得 FastAPI 参数校验。

## 三、方式一：查询对象后删除（单条删除常用）

### 1. 完整删除接口

```python
@app.delete("/book/delete_book/{book_id}")
async def remove_book(
    book_id: int,
    db: AsyncSession = Depends(get_delete_database),
):
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    deleted_id = book.id
    await db.delete(book)
    await db.commit()

    return {"message": "Book deleted", "id": deleted_id}
```

请求示例，ID 应使用实际已有的测试书籍 ID：

```http
DELETE /book/delete_book/1
```

成功后返回 `200 OK`：

```json
{"message": "Book deleted", "id": 1}
```

与当前课堂代码相比，这里明确使用 `book is None` 判断不存在，并在提交成功后返回普通字典。

**适用场景：**删除前需要确认记录存在、检查对象状态、执行逐条业务判断，或需要按照已配置的 ORM 关系处理关联对象。

注意：

- 不需要调用 `db.add(book)`。
- 删除后不要调用 `refresh(book)`；记录已经不存在，不能照搬更新接口中的刷新步骤。
- Python 变量还存在、甚至还能读取某些已加载属性，不代表数据库行仍然存在。
- “先查询、再删除”不自动锁定该记录；并发请求可能在两步之间改变数据。

### 2. 变体：先按条件查询，再逐个删除

如果需要对每个对象执行业务检查，可以先查询一批对象：

```python
async def delete_books_as_objects(db: AsyncSession, publisher: str):
    try:
        result = await db.execute(
            select(Book).where(Book.publisher == publisher)
        )
        books = result.scalars().all()

        for book in books:
            # 有逐条检查规则时，在这里判断；不符合时抛出异常
            await db.delete(book)

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"selected_count": len(books)}
```

这里统一提交；异常会回滚这一批尚未提交的变化。`selected_count` 是本次查到并登记删除的对象数量，不是数据库级联删除的总行数，也不是并发场景下的独立行数核验。

本项目的 SQLAlchemy 2.0.52 `AsyncSession` 没有 `delete_all()` 方法，不能类比 `add_all()` 自行写出这个调用。大量记录只需要统一条件删除时，优先使用下一种方式，避免全部加载到内存。

## 四、方式二：execute(delete(...)) 直接按条件删除

### 1. 按主键直接删除一条记录

```python
async def delete_book_by_id(db: AsyncSession, book_id: int):
    stmt = delete(Book).where(Book.id == book_id)

    try:
        result = await db.execute(stmt)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Book not found")
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"deleted_count": result.rowcount}
```

执行过程：

1. `delete(Book)`：构造针对书籍表的 DELETE。
2. `.where(Book.id == book_id)`：指定要删除的记录。
3. `await db.execute(stmt)`：执行语句，返回执行结果。
4. `await db.commit()`：提交事务，保存结果。

SQL 大致相当于：

```sql
DELETE FROM book WHERE book.id = ?;
```

构造 `stmt` 时不访问数据库，`execute()` 才执行 SQL；但 **execute 成功不等于已经提交**。这种方式不要求先获取 ORM 对象；会话同步策略在某些后端上仍可能附带查询。

`rowcount` 通常表示本条 DELETE 匹配的目标表行数：本表按唯一主键删除时一般是 `0` 或 `1`。它不表示触发器、外键级联等额外删除的总数。当前 SQLite 普通 DELETE 可以这样检查；某些驱动或 RETURNING、批量参数执行场景可能不提供可靠值，甚至返回 `-1`，不能无条件当成实际删除数量。[DELETE 与 rowcount](https://docs.sqlalchemy.org/en/20/tutorial/data_update.html#getting-affected-row-count-from-update-delete)

### 2. 常见条件怎么写

查询时学过的比较、逻辑、范围等条件，同样能用在 DELETE 的 `.where(...)` 中。

以下各例**独立构造语句**；在异步函数内执行 `await db.execute(stmt)`，并提交事务后才会保存删除结果：

```python
# 等值条件：删除指定出版社的书
stmt = delete(Book).where(Book.publisher == "学习出版社")

# 比较条件：删除价格低于 20 的书
stmt = delete(Book).where(Book.price < 20)

# 多个条件同时满足：学习出版社，并且价格不高于 30
stmt = delete(Book).where(
    Book.publisher == "学习出版社",
    Book.price <= 30,
)

# 多个条件满足其一：作者为“张三”或者价格为 0
stmt = delete(Book).where(
    or_(Book.author == "张三", Book.price == 0)
)

# 范围条件：价格在 10 到 20 之间，包含两个边界
stmt = delete(Book).where(Book.price.between(10, 20))

# 模糊条件：书名以“测试-”开头
stmt = delete(Book).where(Book.bookname.like("测试-%"))
```

`.where(条件1, 条件2)` 表示 AND；OR 使用 `or_(...)`。不要用 Python 的 `and`、`or` 拼接 SQLAlchemy 条件。`like()` 中 `%` 匹配任意长度字符串；它不是普通的等值比较。[SQLAlchemy 条件表达式](https://docs.sqlalchemy.org/en/20/core/operators.html)

**条件可能匹配多行。** 按书名、出版社删除不保证只删一条；如果只想删一条明确记录，使用唯一主键。

### 3. 完整条件删除接口：必选出版社，可选价格上限

```python
@app.delete("/book/delete_by_filter")
async def remove_books_by_filter(
    publisher: str = Query(min_length=1, max_length=255),
    max_price: float | None = Query(default=None, ge=0, allow_inf_nan=False),
    db: AsyncSession = Depends(get_delete_database),
):
    conditions = [Book.publisher == publisher]

    if max_price is not None:
        conditions.append(Book.price <= max_price)

    stmt = delete(Book).where(*conditions)
    result = await db.execute(stmt)
    await db.commit()
    return {"deleted_count": result.rowcount}
```

示意请求，实际客户端会对中文参数进行 URL 编码：

```http
DELETE /book/delete_by_filter?publisher=学习出版社&max_price=30
```

该请求删除“学习出版社且价格不高于 30”的所有书。未提供价格上限时，删除这个出版社的所有书；没有匹配行时返回 `200` 和 `{"deleted_count": 0}`。

这里有三个细节：

- `publisher` 没有默认值，是必填参数。缺少它返回 `422`，不会意外退化成没有条件的全表删除。
- `max_price` 用 `is not None` 判断。`0` 是有效上限，写成 `if max_price:` 会错误地跳过条件。
- `*conditions` 是参数解包，把条件列表展开为 `.where(条件1, 条件2, ...)`；两个条件仍然是 AND。

如果以后把全部筛选项都改成可选，应在执行前检查条件列表是否为空，并明确拒绝无条件删除。批量管理接口还应把用户能管理的数据范围加入 WHERE，而不只是检查客户端传了什么条件。

### 4. 按多个 ID 批量删除：使用 in_()

```python
async def delete_books_by_ids(db: AsyncSession, book_ids: list[int]):
    ids = sorted(set(book_ids))  # 去重，便于观察
    if not ids:
        return {"deleted_count": 0}

    stmt = delete(Book).where(Book.id.in_(ids))
    try:
        result = await db.execute(stmt)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"deleted_count": result.rowcount}
```

调用示例：

```python
# 放在异步函数内，假设 1、2 存在，999 不存在
result = await delete_books_by_ids(db, [1, 2, 2, 999])
print(result)  # {'deleted_count': 2}
```

大致对应 `DELETE FROM book WHERE id IN (?, ?, ?)`。本例约定：删除实际存在的记录，不存在的 ID 不报错；空列表不执行删除。

SQLAlchemy 的 `in_([])` 本身也会生成不匹配记录的条件。这里提前返回是为了更清楚地表达空操作，而不是因为空 IN 会删除全表。

不要照搬上一节批量更新的形式，写成 `execute(delete(Book), [{"id": 1}, ...])`，并期待它自动补主键条件；SQLAlchemy 2.x 没有同样的 ORM 按主键字典列表批量 DELETE 模式。本节使用 `WHERE id IN (...)`。[ORM 条件 UPDATE / DELETE](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html#orm-update-and-delete-with-custom-where-criteria)

如果 ID 数量非常多，需要考虑数据库绑定参数数量限制并分批执行。分批执行和分批提交不同：要求全部成功或全部失败时，应在同一事务中执行各批，最后统一提交。

### 5. 扩展：DELETE ... RETURNING 获取删除了哪些记录

数据库支持 RETURNING 时，可以在删除的同时取回指定字段：

```python
async def delete_books_returning(db: AsyncSession, book_ids: list[int]):
    if not book_ids:
        return {"deleted_count": 0, "deleted_books": []}

    stmt = (
        delete(Book)
        .where(Book.id.in_(book_ids))
        .returning(Book.id, Book.bookname)
    )
    try:
        result = await db.execute(stmt)
        deleted_books = [dict(row) for row in result.mappings().all()]
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {
        "deleted_count": len(deleted_books),
        "deleted_books": deleted_books,
    }
```

这里返回的是删除时取回的字段快照，**不是删除后再查询数据库**。记录可能已不存在，快照仍可用于组织响应。不要依赖返回行的顺序与输入 ID 顺序一致。

当前项目环境的 SQLite 支持该示例；PostgreSQL 也支持这种语法，MySQL 不支持同样的 DELETE RETURNING 用法。这个版本用返回行数统计直接删除的目标记录，不依赖 `rowcount`，也不统计级联删除的其他表记录。[DELETE RETURNING](https://docs.sqlalchemy.org/en/20/tutorial/data_update.html#using-returning-with-update-delete)

## 五、方式三：参数化原生 SQL 删除

已有 SQL 脚本或需要数据库专有语法时，可以使用 `text(...)`：

```python
async def delete_books_by_sql(db: AsyncSession, publisher: str, max_price: float):
    stmt = text("""
        DELETE FROM book
        WHERE publisher = :publisher AND price <= :max_price
    """)
    try:
        result = await db.execute(
            stmt,
            {"publisher": publisher, "max_price": max_price},
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"deleted_count": result.rowcount}
```

`:publisher`、`:max_price` 是绑定参数，数据值通过字典传入。不要用 f-string 把用户输入拼进 SQL；绑定参数用于值，不是任意表名、列名的替换工具。[SQLAlchemy text 与绑定参数](https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.text)

这属于直接 SQL 操作，不走 ORM 对象删除流程，也不会自动同步会话中已加载的 `Book` 对象。一般的增删改查优先使用前两种方式。

## 六、旧教程中的 Query.delete()

旧版同步代码经常出现 `query(...).filter(...).delete()`：

```python
from sqlalchemy.orm import Session


def legacy_delete_books(db: Session, publisher: str):
    try:
        deleted_count = (
            db.query(Book)
            .filter(Book.publisher == publisher)
            .delete(synchronize_session="fetch")
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"deleted_count": deleted_count}
```

这是 **同步 Session 的旧式 API**，SQLAlchemy 2.x 仍保留它，但新代码优先使用 `execute(delete(...))`。本项目的 `AsyncSession` 不能写 `await db.query(...)`。

同步对象删除是 `db.delete(book)`，异步对象删除才是 `await db.delete(book)`；不要仅凭方法名判断需不需要 await。[旧式 Query.delete](https://docs.sqlalchemy.org/en/20/orm/queryguide/query.html#sqlalchemy.orm.Query.delete)

## 七、业务中常见的软删除：保留行，标记为已删除

### 1. 硬删除和软删除的区别

| 方式 | 数据库操作 | 查询与恢复 |
| --- | --- | --- |
| 硬删除（物理删除） | `DELETE FROM book ...` | 当前表中不再有该行；提交后无法用 rollback 恢复 |
| 软删除（逻辑删除） | `UPDATE book SET deleted_at = ...` | 行仍在；普通业务查询要过滤，恢复可清除标记 |

课堂代码提到“添加字段记录删除时间”，这就是软删除。它适合回收站、误删恢复等需求，但不能笼统认为所有业务都应使用软删除；它增加查询和约束处理成本，也不等于清除了实际存储的数据。

### 2. 先增加删除时间字段

**以下是扩展方案，当前 Book 模型没有这个字段。** 需要在 `Book` 类内增加：

```python
# 放在 Book 类内部
deleted_at: Mapped[datetime | None] = mapped_column(
    DateTime,
    nullable=True,
    index=True,
    comment="删除时间，NULL 表示未删除",
)
```

还要为已经存在的数据库表迁移新增这一列；`Base.metadata.create_all()` 不会自动给旧表加列。完成模型和表结构变更后，才能运行本节软删除代码。[create_all 与表结构迁移](https://docs.sqlalchemy.org/en/20/core/metadata.html#creating-and-dropping-database-tables)

这里沿用项目 `func.now()` 的时间写法；应用需要约定统一时区，不能因为用了 `DateTime` 就假定所有数据库都会保存带时区的时间。

### 3. 用 UPDATE 实现软删除

```python
async def soft_delete_book(db: AsyncSession, book_id: int):
    stmt = (
        update(Book)
        .where(Book.id == book_id, Book.deleted_at.is_(None))
        .values(deleted_at=func.now())
    )
    try:
        result = await db.execute(stmt)
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Book not found or already deleted")
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"message": "Book deleted", "id": book_id}
```

`deleted_at IS NULL` 表示只删除尚未删除的记录。重复请求不会再次改写原删除时间；本例把不存在和已删除统一返回 `404`。

如果把该函数用于第三节的 DELETE 路由，HTTP 方法仍可使用 DELETE。它对客户端表达“资源已被删除”，数据库内部则通过 UPDATE 实现。

### 4. 查询必须配套过滤

```python
async def list_active_books(db: AsyncSession):
    result = await db.execute(
        select(Book)
        .where(Book.deleted_at.is_(None))
        .order_by(Book.id)
    )
    return result.scalars().all()


async def get_active_book(db: AsyncSession, book_id: int):
    result = await db.execute(
        select(Book).where(Book.id == book_id, Book.deleted_at.is_(None))
    )
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book
```

当前 `db.get(Book, book_id)` 只按主键获取，不会自动排除软删除记录。列表、详情、计数、分页、更新接口都要采用相同的可见性规则，否则数据虽然“删了”，其他接口仍能查询或修改它。

进一步需要考虑：

- 恢复记录时，可将 `deleted_at` 设置回 `None`；原来的唯一键仍可能与后来新增的数据冲突。
- 软删除不会触发数据库 `ON DELETE CASCADE`，因为实际执行的是 UPDATE；关联记录如何处理要另行设计。
- 定期清理软删除记录时，才会执行真正的 DELETE；保留时长和可恢复范围由业务定义。

## 八、条件删除与对象删除不能完全互换

### 1. 已加载对象的会话同步

会话中可能已经加载了某本书，而条件 DELETE 又删除了这行。针对 `execute(delete(Book).where(...))`，SQLAlchemy 提供同步策略：

```python
stmt = (
    delete(Book)
    .where(Book.publisher == "学习出版社")
    .execution_options(synchronize_session="fetch")
)
# 放在异步函数内执行并提交
```

- `"auto"`：默认，根据后端能力选择策略。
- `"fetch"`：借助查询或 RETURNING 确定受影响对象，同步其删除状态。
- `"evaluate"`：尝试在 Python 中判断哪些已加载对象匹配；某些复杂条件不支持。
- `False`：不做同步，内存对象可能保留旧状态。

“同步”指当前会话的对象状态，不等于额外删除其他表。关闭同步后，尤其当前项目设置了 `expire_on_commit=False`，不要把会话中残留的旧对象当作数据库仍有该行的证明。删除后应通过新的查询确认状态，而不是刷新一个已经被删掉的对象。[会话同步策略](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html#selecting-a-synchronization-strategy)

### 2. 外键与级联删除

假如以后增加“书籍评论表”，评论通过外键关联书籍，那么删除书籍时要明确选择：阻止删除、先处理评论，还是让评论一起删除。

| 机制 | 谁执行 | 适用范围 |
| --- | --- | --- |
| ORM 关系中的 `cascade="all, delete"` 等配置 | SQLAlchemy 对象删除流程 | 对象删除会按关系配置处理；不是默认总会删除子记录 |
| 外键中的 `ON DELETE CASCADE` | 数据库 | 外键实际生效时，删父行会删除关联子行 |

`await db.delete(book)` 可参与 ORM 配置的关系级联；`execute(delete(Book).where(...))` 绕过逐个对象的工作单元流程，**不会自动执行 Python 层的关系删除级联**。条件删除若依赖级联，应配置正确的数据库外键规则，或在同一事务中显式处理关联数据。[ORM 与数据库级联的区别](https://docs.sqlalchemy.org/en/20/orm/cascades.html#using-foreign-key-on-delete-cascade-with-orm-relationships)

本项目 `Book.author` 只是作者名字字符串，与 `Author` 表之间没有声明外键和 `relationship()`。删除一本书不会自动删除作者；删除作者也不会自动删除书籍。

SQLite 的外键约束需要在各数据库连接上正确开启 `PRAGMA foreign_keys=ON`；仅写模型外键、或只在另一个命令行连接里开启，不等于应用连接已经启用。[SQLite 外键支持](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#foreign-key-support)

如果删除因外键限制失败，回滚当前事务；当确实是“记录被其他资源引用，不能删除”这一业务冲突时，可对外返回 `409 Conflict`。不要把所有数据库异常都当成记录不存在。

## 九、为什么删除接口使用 HTTP DELETE

### 1. DELETE 直接表达删除指定资源的意图

常见的资源式接口可以写成：

```http
GET    /books/1    获取书籍 1
PUT    /books/1    完整设置书籍 1 的可编辑信息
PATCH  /books/1    修改书籍 1 的部分信息
DELETE /books/1    删除书籍 1
```

HTTP 方法表达操作，URI 标识目标。课堂路径 `/book/delete_book/1` 也能工作；更常见的资源式写法是 `/books/1`，无需把动作名称再写进路径。

DELETE 的协议语义是移除目标资源与当前功能的关联，**不规定数据库必须物理删除一行，也不保证所有底层存储立即清除**。因此，按照接口约定让资源不再可见的软删除，也可以由 DELETE 接口实现。[RFC 9110：DELETE](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.5)

### 2. DELETE 具有幂等语义

幂等是指：在没有其他操作干扰的前提下，相同请求执行一次或多次，预期的资源修改效果相同。

```text
初始状态：书籍 1 存在

第一次 DELETE /books/1：书籍 1 不存在，返回 200 或 204
第二次 DELETE /books/1：书籍 1 仍不存在，可以返回 404

最终状态都是“书籍 1 不存在”，仍符合幂等语义
```

**幂等不要求每次状态码、响应体完全一致。** 第三节的“第一次成功、第二次 404”设计是合理的；也可以选择对不存在的资源返回 `204`，表达“现在已经不存在”。关键是接口约定一致。[RFC 9110：幂等方法](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)

幂等设计有助于处理“服务器已经删除成功，但客户端没有收到响应”的重试。它不表示所有操作可以无限重试，也不表示并发修改不会发生。

`@app.delete(...)` 只负责注册路由，不会自动实现删除或保证幂等。例如“每调用一次就删除当前最旧的一本书”，连续调用会删掉不同记录，不符合对同一个确定资源重复 DELETE 的幂等预期。

条件删除也应有明确范围。若两次请求之间新插入了符合条件的数据，第二次删除可能处理新增记录，这是两次请求之间发生了其他操作，不能简单据此否定 DELETE 的幂等语义。

### 3. 为什么不用 GET，能不能用 POST

| 方法 | 通常表达的意图 | 与删除的关系 |
| --- | --- | --- |
| GET | 读取资源，属于安全方法 | 不应用来请求删除；浏览器预取、爬虫访问都可能触发 GET |
| POST | 提交创建请求或业务动作 | 可以定义批量处理等业务动作，但协议不保证幂等 |
| PUT / PATCH | 设置或修改资源状态 | 常用于修改；纯粹删除资源时 DELETE 更直接 |
| DELETE | 删除指定资源 | 与删除接口意图一致，应按幂等语义设计 |

“安全方法”中的安全是指客户端不请求改变服务器状态；DELETE 会改变状态，所以它**幂等，但不是安全方法**。[HTTP 安全方法](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.1)

技术上，FastAPI 不会阻止开发者在 POST 路由里执行数据库 DELETE。但对于删除指定资源，使用 DELETE 能让接口文档和调用者更容易理解行为。

### 4. 删除成功必须返回 204 吗

不必须，常见设计如下：

| 状态码 | 含义 | 示例 |
| --- | --- | --- |
| `200 OK` | 删除已经完成，返回结果说明 | `{"message": "Book deleted"}` 或删除数量 |
| `204 No Content` | 删除已经完成，不返回响应体 | 空响应，不能附带 JSON，连 `null` 也不是所需的空响应 |
| `202 Accepted` | 已接受请求，实际删除尚未完成 | 已登记后台任务；不能冒充“已经删除成功” |
| `404 Not Found` | 没有找到目标资源 | 本节单条删除的约定 |
| `409 Conflict` | 当前资源状态与删除要求冲突 | 业务明确禁止删除仍被引用的记录 |
| `422 Unprocessable Content` | FastAPI 参数校验未通过 | ID 不是整数、缺少必填筛选条件等 |

前面三种成功响应均符合 DELETE 的语义，选择取决于是否执行完成、是否需要返回内容。[DELETE 响应语义](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.5)

如果选择 `204`，可以这样写一个接口变体：

```python
@app.delete("/books/{book_id}", status_code=204, response_class=Response)
async def remove_book_no_content(
    book_id: int,
    db: AsyncSession = Depends(get_delete_database),
):
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    await db.delete(book)
    await db.commit()
    return Response(status_code=204)
```

这一版显式返回空响应。不要一边声明 `status_code=204`，一边返回 `{"message": "success"}`。[FastAPI 响应状态码](https://fastapi.tiangolo.com/tutorial/response-status-code/)

### 5. DELETE 参数放在哪里

单条删除通常通过路径传 ID；简单条件删除可以使用查询参数，例如第四节的出版社和价格上限。

DELETE 请求体没有通用定义的语义，一些客户端、代理或网关对它的支持也不同。因此不能简单说“DELETE 绝对不能带请求体”，但也不应默认依赖它。大量 ID 或复杂条件可以定义一个明确的 POST 批量删除任务接口，由请求体承载参数，并单独设计重试和结果查询规则。[DELETE 请求内容语义](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.3.5)

## 十、删除操作常见问题

### 1. 忘记 WHERE 会怎样

```python
# 只构造语句；不要随意执行
stmt = delete(Book)
# 对应 DELETE FROM book，没有 WHERE，执行并提交后会删除全表记录
```

DELETE 不会因为模型有主键，就自动知道要删哪一行。批量删除前可以使用相同条件做 SELECT 核对范围；但预先查询的结果不等于锁定，最终结果仍取决于执行时的数据和事务。

### 2. del book、清空列表能删除数据库吗

不能。`del book` 删除的是 Python 变量绑定；对查询结果列表调用 `clear()` 只是清空这个列表。普通查询结果不是一个“与数据库自动双向同步的表”。

数据库行删除需要调用 ORM 删除方法或执行 DELETE。关系集合上的 `delete-orphan` 等特殊规则属于单独配置的 ORM 行为，不能套用到普通结果列表。

### 3. 删除失败或后悔了，能恢复吗

在 SQLite 事务中，可以先 flush，再回滚观察效果：

```python
async def demonstrate_delete_rollback(db: AsyncSession, book_id: int):
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    try:
        await db.delete(book)
        await db.flush()     # 当前事务已执行 DELETE
    finally:
        await db.rollback()  # 本练习不提交，撤销当前事务的修改

    return await db.get(Book, book_id)  # 无其他请求干扰时，可以重新取得该书
```

这个演示应使用独立会话，避免把其他尚未提交的修改一起回滚。**已经 commit 成功的硬删除，不能再用 rollback 撤销**；需要依靠备份、归档或其他恢复机制。软删除则可以按业务规则恢复标记。

事务会话只关闭、不提交时，也不会把尚未提交的删除永久保存。显式提交和异常回滚有助于把成功与失败边界写清楚。

### 4. 删除数据不等于删除表

`DELETE FROM book WHERE ...` 删除记录，表结构仍存在；`DROP TABLE book` 删除表结构及其中数据，不是普通删除接口的实现方式。

也不要把 `TRUNCATE` 当成可移植的条件删除方案：SQLite 不支持该语句，它也不是带 WHERE 的逐行删除。其他数据库对事务、自增计数等行为各有规则，不能与本节 DELETE 混为一谈。[SQLite 支持的 SQL 语句](https://www.sqlite.org/lang.html)

## 十一、方法选择与练习

| 场景 | 优先选择 |
| --- | --- |
| 删除一条记录，需读取旧值或做对象级检查 | `get()` → `await db.delete(book)` → `commit()` |
| 一批对象都需要逐条检查或 ORM 关系处理 | 条件查询后循环 `await db.delete(book)`，统一提交 |
| 按出版社、价格、时间等条件删除 | `execute(delete(Book).where(...))` |
| 已知多个 ID，删除存在的记录 | `delete(Book).where(Book.id.in_(ids))` |
| 要知道实际删除了哪些行，数据库支持 RETURNING | `delete(...).returning(...)` |
| 需要直接执行已有 SQL | 参数化 `text(...)` |
| 需要回收站、标记删除或恢复 | 添加删除字段，用 UPDATE 软删除，并配套查询过滤 |
| 阅读旧版同步项目 | 认识 `Query.delete()` |

使用专门创建的测试书籍练习，ID 以新增接口返回值为准；不同删除练习需要重新准备数据：

1. 删除已有书籍，观察成功响应，再查询确认它不再存在。
2. 对同一 ID 再次删除，观察 `404`，理解它为什么不违反幂等性。
3. 使用 `204` 版本，确认响应体为空。
4. 准备同出版社不同价格、不同出版社同价格的书，验证 AND 条件不会误删其他记录。
5. 条件删除传 `max_price=0`，确认只处理价格不高于零的目标书籍；省略必填出版社应返回 `422`。
6. 用重复 ID、缺失 ID、空列表测试批量删除，核对返回数量。
7. 运行独立的 flush + rollback 演示，比较执行 DELETE 与提交事务的区别。
8. 在单独的测试表完成软删除字段迁移后，验证物理行仍存在、业务列表和详情查不到它。

关联复习：[条件查询](../19-FastAPI进阶-ORM操作数据-条件查询/19-FastAPI进阶-ORM操作数据-条件查询.md)、[新增数据与事务](../25-FastAPI进阶-ORM操作数据-新增数据/25-FastAPI进阶-ORM操作数据-新增数据.md)、[更新数据与 HTTP PUT/PATCH](../26-FastAPI进阶-ORM操作数据-更新数据/26-FastAPI进阶-ORM操作数据-更新数据.md)。
