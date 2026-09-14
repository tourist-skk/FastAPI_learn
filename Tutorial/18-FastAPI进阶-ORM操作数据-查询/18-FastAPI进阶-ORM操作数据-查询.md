# 18-FastAPI进阶-ORM操作数据-查询

ORM 操作包括查询、添加、更新、删除。本节继续使用 `Book` 模型和异步会话 `AsyncSession`，重点学习查询。

ORM 对象与查询返回值的基础讲解已抽出，建议按顺序阅读：

- [08-ORM对象](../00-python基础补充/08-ORM对象.md)：模型类、实例、字典与 JSON。
- [09-SQLAlchemy查询结果与取值](../00-python基础补充/09-SQLAlchemy查询结果与取值.md)：`Result`、`ChunkedIteratorResult`、`CursorResult`，以及 `scalar()` 等取值方法。

先修正核心语句：方法名是 `execute`，并且它返回的是**查询结果对象**，不是直接返回一个 ORM 对象。

```python
stmt = select(Book)             # 构造查询语句，此时还没有执行查询
result = await db.execute(stmt) # 执行查询，取得 Result 结果对象
books = result.scalars().all()  # 取出其中的 Book 实例，得到列表
```

## 一、代码准备

沿用第 16、17 节的 `Book`、`app` 和 `get_database`，不需要重新建表。下面的查询函数可以放在它们定义之后。

需要的导入：

```python
from fastapi import Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
```

每个示例中的 `db` 都是当前请求使用的 `AsyncSession`，由依赖注入取得。含 `await` 的代码片段需要放在异步函数内执行。

为了理解结果，假设表中已有下面三本书，时间字段略去：

```text
id=1，bookname="Python for Beginners"，author="John Doe"，price=30，publisher="XinHua"
id=2，bookname="FastAPI Guide"，author="Jane Doe"，price=50，publisher="XinHua"
id=3，bookname="SQL Basics"，author="John Doe"，price=20，publisher="TechPress"
```

这只是说明数据，不会自动插入你的数据库。以下结果说明以这组数据为例。

## 二、获取所有数据

```python
async def query_all(db: AsyncSession):
    stmt = select(Book).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

`select(Book)` 查询书籍实体，`order_by(Book.id)` 按主键升序排列。返回 `Book` 实例列表；没有数据时返回 `[]`。

也可以简写为：

```python
async def query_all_short(db: AsyncSession):
    result = await db.scalars(select(Book).order_by(Book.id))
    return result.all()
```

`await db.scalars(stmt)` 相当于执行查询后直接取得标量结果视图。注意区分会执行查询的 `db.scalars()`，与只整理已有结果的 `result.scalars()`。

## 三、获取单条数据

### 1. 按主键查询：db.get()

```python
async def query_by_id(db: AsyncSession, book_id: int):
    return await db.get(Book, book_id)
```

- `Book`：要查询的模型。
- `book_id`：主键值。
- 找到时返回 `Book` 实例，没有时返回 `None`。

`get()` 是会话的方法，原笔记中的 `scalars().get(模型类, 主键值)` 应改为 `await db.get(Book, 主键值)`。它适合按主键查询，不能用来按书名等普通字段查询。

会话中如果已经存在该主键对应的实例，且对象没有过期，`get()` 可以直接复用，不一定再次发送 SQL。

### 2. 取第一条：scalars().first()

```python
async def query_first(db: AsyncSession):
    stmt = (
        select(Book)
        .where(Book.author == "John Doe")
        .order_by(Book.id)
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalars().first()
```

查询 John Doe 的第一本书，示例中得到 `id=1` 的实例；没有符合条件的数据时返回 `None`。

`first()` 只取结果中的第一个元素，不检查是否存在其他匹配项。SQLAlchemy 2.x 的这个结果方法不会自动向 SQL 添加 `LIMIT 1`，所以代码中显式写了 `limit(1)`。没有 `order_by` 时，不应假设哪条记录是“第一条”。

### 3. 最多允许一条：scalar_one_or_none()

```python
async def query_one_or_none(db: AsyncSession, book_id: int):
    result = await db.execute(select(Book).where(Book.id == book_id))
    return result.scalar_one_or_none()
```

- 0 条：返回 `None`。
- 1 条：返回该 `Book` 实例。
- 多于 1 条：抛出 `MultipleResultsFound`。

它等价于 `result.scalars().one_or_none()`。按主键查询不会匹配多条，但换成书名等条件后，这种检查可以发现“原本期望唯一，实际却重复”的情况。不要提前加 `limit(1)` 来掩盖重复结果。

### 4. 必须恰好一条：scalar_one()

```python
async def query_exactly_one(db: AsyncSession, book_id: int):
    result = await db.execute(select(Book).where(Book.id == book_id))
    return result.scalar_one()
```

恰好一条时返回实例；没有结果时抛出 `NoResultFound`，多条时抛出 `MultipleResultsFound`。适合业务要求必须存在的情况；若用于接口，需要根据业务处理异常。

对于 `select(Book)`，`result.first()` 得到的是一行 `Row`，`result.scalars().first()` 得到的才是 `Book` 实例。[SQLAlchemy 结果方法说明](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Result)。

## 四、条件查询

### 1. 多个条件同时满足：where()

```python
async def query_price_range(db: AsyncSession):
    stmt = select(Book).where(
        Book.price >= 20,
        Book.price <= 40,
        Book.author == "John Doe",
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

多个条件以 SQL 的 `AND` 连接，示例中返回 `id=1、3` 的书籍。连续调用多个 `where()` 也表示同时满足。

常用比较有 `==`、`!=`、`>`、`>=`、`<`、`<=`。价格范围也可写成 `Book.price.between(20, 40)`，包含两个边界。

### 2. 满足任意条件：or_()

```python
async def query_any_condition(db: AsyncSession):
    stmt = select(Book).where(
        or_(Book.price < 30, Book.publisher == "XinHua")
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

价格低于 30，或者出版社是 XinHua，满足任意一个即可；示例中三本书都符合。构造 SQL 条件时不要使用 Python 的 `and`、`or` 代替 SQLAlchemy 的条件组合。

### 3. 匹配一组值：in_()

```python
async def query_ids(db: AsyncSession):
    stmt = select(Book).where(Book.id.in_([1, 3])).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

等价于 SQL 条件 `id IN (1, 3)`，返回对应的两本书。

### 4. 模糊查询：like()

```python
async def query_keyword(db: AsyncSession, keyword: str):
    stmt = select(Book).where(
        Book.bookname.like(f"%{keyword}%")
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

传入 `"Python"` 时查询书名包含 Python 的书籍。

`%` 匹配任意长度字符，`_` 匹配单个字符；因此输入中自带这两个字符时，也会参与通配匹配。如果希望把用户输入当作普通文本包含查询，可以改为 `Book.bookname.contains(keyword, autoescape=True)`。

## 五、排序与分页

### 1. 排序：order_by()

```python
async def query_sorted(db: AsyncSession):
    stmt = select(Book).order_by(Book.price.desc(), Book.id.asc())
    result = await db.execute(stmt)
    return result.scalars().all()
```

`desc()` 表示降序，`asc()` 表示升序。先按价格从高到低排列，同价时按主键升序，示例顺序是 `id=2、1、3`。

### 2. 分页：offset() 和 limit()

```python
async def query_page(db: AsyncSession, page: int, page_size: int):
    offset = (page - 1) * page_size
    stmt = (
        select(Book)
        .order_by(Book.id)
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return result.scalars().all()
```

`page` 从 1 开始；`offset` 表示跳过多少行，`limit` 表示最多取多少行。第 2 页、每页 2 条时，跳过前 2 条，只得到 `id=3`。

调用者应保证 `page >= 1`、`page_size >= 1`。分页要显式排序，避免依赖数据库未指定的返回顺序；最后一节用 `Query` 校验这些参数。

## 六、查询指定字段

### 1. 只查书名

```python
async def query_names(db: AsyncSession):
    result = await db.execute(select(Book.bookname).order_by(Book.id))
    return result.scalars().all()
```

返回字符串列表。与 `select(Book)` 相比，这条 SQL 只选择书名字段。

### 2. 同时查主键、书名和价格

```python
async def query_fields(db: AsyncSession):
    stmt = select(Book.id, Book.bookname, Book.price).order_by(Book.id)
    result = await db.execute(stmt)
    rows = result.mappings().all()
    return [dict(row) for row in rows]
```

`mappings()` 把每行作为支持字段名访问的 `RowMapping` 读取，再通过 `dict(row)` 转成普通字典，便于返回 JSON：

```text
[
    {"id": 1, "bookname": "Python for Beginners", "price": 30.0},
    {"id": 2, "bookname": "FastAPI Guide", "price": 50.0},
    {"id": 3, "bookname": "SQL Basics", "price": 20.0}
]
```

如果改用 `result.all()`，每行就是包含三个元素的 `Row`，可以通过 `row.id`、`row.bookname` 或位置读取。这里不要使用默认的 `scalars()`，否则只保留主键。

## 七、统计查询

### 1. 查询总条数：count()

```python
async def query_count(db: AsyncSession):
    stmt = select(func.count()).select_from(Book)
    result = await db.execute(stmt)
    return result.scalar_one()
```

生成类似 `SELECT count(*) FROM book` 的语句，示例返回整数 `3`，空表返回 `0`。

`select_from(Book)` 指明统计哪张表。这里的结果是一行一个数字，所以 `scalar_one()` 取得的是数字，不是 `Book` 实例。不要用 `result.rowcount` 统计普通 SELECT 的查询条数。

### 2. 平均价、最高价和最低价

```python
async def query_stats(db: AsyncSession):
    stmt = select(
        func.avg(Book.price).label("avg_price"),
        func.max(Book.price).label("max_price"),
        func.min(Book.price).label("min_price"),
    )
    result = await db.execute(stmt)
    return dict(result.mappings().one())
```

`func` 用于构造数据库函数调用，`label()` 为查询结果命名。这里一行包含三个值，因此使用 `mappings().one()` 保留全部字段。空表的这三项统计值均为 `None`。

### 3. 按出版社统计：group_by()

```python
async def query_by_publisher(db: AsyncSession):
    stmt = (
        select(Book.publisher, func.count().label("book_count"))
        .group_by(Book.publisher)
        .order_by(Book.publisher)
    )
    result = await db.execute(stmt)
    return [dict(row) for row in result.mappings().all()]
```

`group_by(Book.publisher)` 把相同出版社的行分为一组，每组统计书籍数。示例中 TechPress 有 1 本，XinHua 有 2 本。

如果只保留书籍数大于 1 的出版社，可以在语句上追加 `.having(func.count() > 1)`；`where()` 在分组前过滤行，`having()` 对分组后的结果进行过滤。

## 八、将查询放入 FastAPI 路由

下面调用上面定义的查询函数。若脚本已有 `/book/books` 路由，请替换旧路由，避免重复注册相同路径。

```python
@app.get("/book/books")
async def get_book_list(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_database, scope="function"),
):
    books = await query_page(db, page, page_size)
    total = await query_count(db)
    return {"total": total, "page": page, "page_size": page_size, "items": books}


@app.get("/book/books/{book_id}")
async def get_book_detail(
    book_id: int,
    db: AsyncSession = Depends(get_database, scope="function"),
):
    book = await query_by_id(db, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="书籍不存在")
    return book
```

请求示例：

- `GET /book/books?page=2&page_size=2`：获取第 2 页，最多返回 2 本。
- `GET /book/books/1`：按主键查询书籍。
- 主键不存在时返回 404；列表没有匹配数据时返回空列表。

这里的 `Book` 只有普通列，查询后属性已经加载，FastAPI 可以将实例内容序列化为 JSON。后续涉及关系属性或复杂返回结构时，可再学习响应模型和关系加载。

纯查询不需要为了“保存结果”而调用 `commit()`。第 17 节依赖中的提交是统一事务管理策略；本节重点是查询语句与结果读取方式。

参考资料：

- [SQLAlchemy ORM 查询指南](https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html)
- [SQLAlchemy 结果对象与读取方法](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Result)
- [SQLAlchemy Session.get](https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.get)
