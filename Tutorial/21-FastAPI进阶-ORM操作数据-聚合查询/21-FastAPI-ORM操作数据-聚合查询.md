# 21-FastAPI-ORM操作数据-聚合查询

## 一、什么是聚合查询

聚合查询是把多条记录汇总成统计结果，例如书籍数量、价格总和、平均价格、最高价和最低价。

普通查询 `select(Book)` 可以返回一个个 `Book` 对象；聚合查询 `select(func.count(Book.id))` 返回的是数量这样的统计值。

核心写法是 **`func.函数名(模型类.属性)`**，例如 `func.sum(Book.price)`。其中 `Book.price` 表示数据库中的价格列。

`func` 是 SQLAlchemy 提供的 SQL 函数入口。`func.sum(Book.price)` 只是构造 SQL 表达式；调用 `await db.execute(stmt)` 时，数据库才执行计算，并把结果传回 Python，无须先加载全部书籍对象。[SQLAlchemy 查询教程](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html#working-with-sql-functions)

本节沿用已有的 `Book`、`app` 和 `get_database`，补充以下导入。下面的查询函数接在模型定义后即可使用，不需要重新创建引擎。

```python
from fastapi import Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
```

每个函数的 `db: AsyncSession` 表示接收一个异步数据库会话。普通函数调用时需要手动传入 `db`，路由中则可以通过 `Depends(get_database)` 获取。

下文示例结果以当前七条测试数据为例：价格为 `30、50、250、150、100、39、59`。修改数据库后，统计值也会改变。

## 二、常用聚合函数

### 1. count()：统计数量

```python
async def query_count(db: AsyncSession):
    stmt = select(func.count(Book.id))
    result = await db.execute(stmt)
    return result.scalar_one()
```

对应 SQL：

```sql
SELECT count(book.id) FROM book;
```

这里统计 `id` 不为 `NULL` 的记录数量。因为主键不允许为 `NULL`，所以结果就是书籍总数，当前返回 `7`。

`result` 仍然按行组织，结果可以理解为 `[(7,)]`。`scalar_one()` 要求恰好有一行，并取出这一行的第一列，因此得到整数 `7`。

也可以用 `COUNT(*)` 统计所有行：

```python
stmt = select(func.count()).select_from(Book)
```

`func.count()` 表示 `COUNT(*)`；`select_from(Book)` 明确指定从 `book` 表统计。这里没有引用模型的列，不能省略表来源。

**扩展：统计不同作者的数量。**

```python
async def query_author_count(db: AsyncSession):
    stmt = select(func.count(distinct(Book.author)))
    result = await db.execute(stmt)
    return result.scalar_one()
```

`distinct(Book.author)` 表示对作者去重，相当于 `COUNT(DISTINCT author)`。同一作者写了多本书也只计一次，当前返回 `5`。

### 2. sum()：求和

```python
async def query_sum(db: AsyncSession):
    stmt = select(func.sum(Book.price))
    result = await db.execute(stmt)
    return result.scalar_one()
```

对应 `SELECT sum(book.price) FROM book`，把所有书籍的价格相加，当前返回 `678.0`。这里没有销量字段，所以这个值只是价格之和，并不代表销售额。

### 3. avg()：求平均值

```python
async def query_avg(db: AsyncSession):
    stmt = select(func.avg(Book.price))
    result = await db.execute(stmt)
    return result.scalar_one()
```

对应 `SELECT avg(book.price) FROM book`，当前结果约为 `96.857142857`，即 `678 ÷ 7`。`avg()` 不会自动保留两位小数。

### 4. max()：求最大值

```python
async def query_max(db: AsyncSession):
    stmt = select(func.max(Book.price))
    result = await db.execute(stmt)
    return result.scalar_one()
```

对应 `SELECT max(book.price) FROM book`，当前返回最高价格 `250.0`。

**这里返回的是价格，不是最高价书籍的 `Book` 对象**，因此不能对结果访问 `.bookname`。如果需要书籍详情，需要另外编写查询书籍的语句。

### 5. min()：求最小值

```python
async def query_min(db: AsyncSession):
    stmt = select(func.min(Book.price))
    result = await db.execute(stmt)
    return result.scalar_one()
```

对应 `SELECT min(book.price) FROM book`，当前返回最低价格 `30.0`，同样只返回统计值。

### 6. 空表和 NULL 怎么处理

上述未分组、未使用 `HAVING` 的聚合查询，即使表为空，也会返回一行统计结果：

- `count()` 返回 `0`。
- `sum()`、`avg()`、`max()`、`min()` 返回 SQL 的 `NULL`，在 Python 中表现为 `None`。
- 指定列时，这些聚合函数会忽略该列的 `NULL`；`COUNT(*)` 统计所有行。例如价格为 `10、20、NULL`，平均值是 `15`，不是 `10`。

当前模型的价格列不允许为空，但空表或者 `where()` 没有匹配到记录时，仍然需要考虑 `None`。[SQLite 聚合函数说明](https://www.sqlite.org/lang_aggfunc.html)

此时 `scalar_one()` 可以返回 `None`：它要求的是“恰好一行”，并不要求这一行的值非空。

如果希望求和无数据时返回 `0`，可以这样写：

```python
async def query_sum_or_zero(db: AsyncSession):
    stmt = select(func.coalesce(func.sum(Book.price), 0))
    result = await db.execute(stmt)
    return result.scalar_one()
```

`coalesce(a, b)` 返回第一个不是 `NULL` 的参数：先求和，如果结果是 `NULL`，就使用 `0`。它是辅助处理空值的 SQL 函数，本身不是聚合函数。

## 三、先筛选，再聚合

需求：只统计“测试出版社”的书籍数量。

```python
async def query_filtered_count(db: AsyncSession):
    stmt = select(func.count(Book.id)).where(
        Book.publisher == "测试出版社"
    )
    result = await db.execute(stmt)
    return result.scalar_one()
```

逻辑上先通过 `where()` 筛选记录，再对剩下的记录执行 `count()`，当前返回 `2`。之前学习的比较、模糊、包含等条件都可以放进 `where()`。

## 四、一次查询多个统计值

```python
async def query_stats(db: AsyncSession):
    stmt = select(
        func.count(Book.id).label("book_count"),
        func.sum(Book.price).label("total_price"),
        func.avg(Book.price).label("avg_price"),
        func.max(Book.price).label("max_price"),
        func.min(Book.price).label("min_price"),
    )
    result = await db.execute(stmt)
    return dict(result.mappings().one())
```

- `select(...)` 接收多个表达式，一次查询返回五列统计结果。
- `.label("book_count")` 给结果列取别名，不会修改数据库字段名。
- `.mappings()` 将结果按“列名 → 值”的映射形式提供。
- `.one()` 取出唯一一行；`dict(...)` 将这一行转成普通字典，方便返回 JSON。

结果类似：

```json
{
  "book_count": 7,
  "total_price": 678.0,
  "avg_price": 96.85714285714286,
  "max_price": 250.0,
  "min_price": 30.0
}
```

这里不能使用 `scalar_one()` 或 `scalars().all()` 来获取完整结果：它们默认只取每行第一列，其他统计列就不会出现在返回值中。

本节采用 `await db.execute()` 获取已缓冲的结果，后面的 `scalar_one()`、`mappings()`、`one()` 和 `all()` 不需要加 `await`。

## 五、group_by()：分组聚合

需求：分别统计每家出版社的书籍数量和平均价格。

```python
async def query_publisher_stats(db: AsyncSession):
    stmt = select(
        Book.publisher,
        func.count(Book.id).label("book_count"),
        func.avg(Book.price).label("avg_price"),
    ).group_by(Book.publisher).order_by(Book.publisher)

    result = await db.execute(stmt)
    return [dict(row) for row in result.mappings().all()]
```

`group_by(Book.publisher)` 把出版社相同的记录归为一组，聚合函数分别在每组内部计算。`order_by()` 只用于固定结果顺序。

不分组时是整张表汇总为一行；分组后每家出版社对应一行，因此使用 `.all()` 取出多行。当前结果：

```json
[
  {"publisher": "Guang Dong", "book_count": 2, "avg_price": 125.0},
  {"publisher": "XinHua", "book_count": 3, "avg_price": 110.0},
  {"publisher": "测试出版社", "book_count": 2, "avg_price": 49.0}
]
```

分组查询中，选择的普通列应放入 `group_by()`，其余列使用聚合函数。例如这里选择了 `Book.publisher`，也按它分组。不要随意再选择 `Book.bookname`，因为一组可能包含多本书，无法确定应该返回哪个书名。

空表没有分组，因此该函数返回 `[]`。

## 六、having()：筛选聚合后的分组

### 1. 为什么筛选统计值要使用 having()

需求：只保留书籍数量大于两本的出版社。

```python
async def query_publisher_having(db: AsyncSession):
    stmt = select(
        Book.publisher,
        func.count(Book.id).label("book_count"),
    ).group_by(Book.publisher).having(
        func.count(Book.id) > 2
    ).order_by(Book.publisher)

    result = await db.execute(stmt)
    return [dict(row) for row in result.mappings().all()]
```

当前返回 `[{"publisher": "XinHua", "book_count": 3}]`。

`where()` 筛选参与统计的原始记录，`having()` 筛选统计完成后的组。例如“价格大于 50 的书”用 `where(Book.price > 50)`；“书籍数量大于 2 的出版社”用 `having(func.count(Book.id) > 2)`。

单看一本书，可以判断它的价格，却无法直接判断“它所属的出版社有几本书”。后一个条件需要先分组、计算每组数量，再判断是否保留整组，因此使用 `having()`。

逻辑处理顺序可以理解为：**读取记录 → WHERE 筛选 → GROUP BY 分组 → 聚合计算 → HAVING 筛选组 → ORDER BY 排序**。这是帮助理解结果的逻辑顺序，数据库实际执行时可能优化处理过程。[SQLAlchemy 分组与 HAVING](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html#aggregate-functions-with-group-by-having)

### 2. 在 group_by() 后使用 where()，筛选普通字段会怎样

**可以正常执行，但仍然在分组前筛选原始记录，不是在分组后筛选统计结果。**

```python
async def query_group_then_where(db: AsyncSession):
    stmt = select(
        Book.publisher,
        func.count(Book.id).label("book_count"),
    ).group_by(Book.publisher).where(
        Book.price >= 50
    ).order_by(Book.publisher)

    result = await db.execute(stmt)
    return [dict(row) for row in result.mappings().all()]
```

虽然代码把 `.where()` 写在 `.group_by()` 后面，生成的 SQL 仍然是：

```sql
SELECT book.publisher, count(book.id) AS book_count
FROM book
WHERE book.price >= 50
GROUP BY book.publisher
ORDER BY book.publisher;
```

沿用本节七条示例数据，返回：

```json
[
  {"publisher": "Guang Dong", "book_count": 2},
  {"publisher": "XinHua", "book_count": 2},
  {"publisher": "测试出版社", "book_count": 1}
]
```

其中 XinHua 原本有三本书，价格分别为 `30、50、250`。`WHERE` 先排除价格为 `30` 的书，因此最终计数为 `2`。这里统计的是“每家出版社价格不低于 50 的书籍数”。

**链式调用是在构造 SQL，不是按代码从左到右立即处理数据库记录。** 把 `.where(...)` 移到 `.group_by(...)` 前面，本例的含义和结果都不变。

### 3. 在 group_by() 后使用 where()，直接筛选聚合值会怎样

下面是一个错误示例：

```python
async def query_group_where_error(db: AsyncSession):
    stmt = select(
        Book.publisher,
        func.count(Book.id).label("book_count"),
    ).group_by(Book.publisher).where(
        func.count(Book.id) > 2  # 错误：当前查询的聚合值放进了 WHERE
    )

    result = await db.execute(stmt)  # 执行时会报错
    return [dict(row) for row in result.mappings().all()]
```

这段 Python 可以构造语句，但生成的 SQL 包含：

```sql
SELECT book.publisher, count(book.id) AS book_count
FROM book
WHERE count(book.id) > 2
GROUP BY book.publisher;
```

`WHERE` 所处的阶段还没有本次分组的计数，不能直接使用这个聚合表达式。项目当前 SQLite 环境中，执行时会抛出 `sqlalchemy.exc.OperationalError`，底层错误信息为：

```text
misuse of aggregate: count()
```

**结果是执行失败，不是返回空列表，也不会自动改成 HAVING。** 将 `.where(func.count(Book.id) > 2)` 改成 `.having(func.count(Book.id) > 2)` 即可表达本节原需求。

### 4. where() 和 having() 可以同时使用

例如，先选出价格不低于 50 的书，再只保留这类书超过两本的出版社：

```python
stmt = (
    select(Book.publisher, func.count(Book.id).label("book_count"))
    .where(Book.price >= 50)
    .group_by(Book.publisher)
    .having(func.count(Book.id) > 2)
)
```

执行方式同前面的函数。本节示例数据中，`WHERE` 筛选后各出版社的计数分别为 `2、2、1`，没有一组满足大于 `2`，因此这次查询正常执行，最终返回 `[]`。

## 七、接入 FastAPI 路由

把上面的查询函数放到已有脚本中后，可以添加以下路由：

```python
@app.get("/book/stats")
async def get_book_stats(
    db: AsyncSession = Depends(get_database),
):
    return await query_stats(db)


@app.get("/book/stats/publishers")
async def get_publisher_stats(
    db: AsyncSession = Depends(get_database),
):
    return await query_publisher_stats(db)
```

`Depends(get_database)` 让 FastAPI 获取会话并赋给参数 `db`；`await query_stats(db)` 将会话传给查询函数，等待统计结果后返回 JSON。

启动原有应用后，访问 `/book/stats` 查看整体统计，访问 `/book/stats/publishers` 查看按出版社分组的统计。
