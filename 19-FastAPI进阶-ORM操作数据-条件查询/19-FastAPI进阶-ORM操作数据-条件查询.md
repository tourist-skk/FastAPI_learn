# 19-FastAPI进阶-ORM操作数据-条件查询

条件查询是在数据库中筛选符合要求的数据。本节沿用 `Book` 模型，主要学习比较条件。

核心写法：

```python
stmt = select(Book).where(Book.price >= 30)
result = await db.execute(stmt)
books = result.scalars().all()
```

`where()` 对应 SQL 的 `WHERE`。它接收条件表达式；`select()` 和 `where()` 只是构造语句，执行到 `await db.execute(stmt)` 时才查询数据库。

## 一、条件查询包括哪些

可以按用途把常见条件整理为以下几类：

1. **比较条件**：`==`、`!=`、`>`、`<`、`>=`、`<=`。例如 `Book.price >= 30`，查询价格不低于 30 的书。
2. **范围条件**：`between()`。例如 `Book.price.between(20, 40)`，查询价格在 20 到 40 之间的书，包含两个边界。
3. **模糊与字符串匹配**：`like()`、`ilike()`、`contains()`、`startswith()`、`endswith()`。例如 `Book.bookname.like("%Python%")`，查询书名包含 Python 的书。
4. **集合包含条件**：`in_()`、`not_in()`。例如 `Book.id.in_([1, 3])`，查询主键属于这组值的书。
5. **空值条件**：`is_(None)`、`is_not(None)`。例如 `Book.publisher.is_(None)`，查询出版社为空的记录。
6. **逻辑组合条件（与、或、非）**：`and_()`、`or_()`、`not_()`，也可使用 `&`、`|`、`~` 组合 SQLAlchemy 条件。

原笔记的“与非查询”应整理为“与、或、非”：`&` 表示同时满足，`|` 表示满足其一，`~` 表示取反。

这些分类可以组合使用，不是互相排斥的。本节重点讲六种比较运算符，并补充范围和空值判断；模糊、包含、复杂逻辑查询可继续单独学习。[SQLAlchemy 条件运算符](https://docs.sqlalchemy.org/en/20/core/operators.html)。

## 二、示例准备：看清比较是否包含边界

沿用前两节的 `Book`、`app` 和 `get_database`，需要以下导入：

```python
from fastapi import Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
```

假设数据库有三本书：

```text
id=1，书名="Python for Beginners"，价格=30，出版社="XinHua"
id=2，书名="FastAPI Guide"，价格=50，出版社="XinHua"
id=3，书名="SQL Basics"，价格=20，出版社="TechPress"
```

以下结果说明基于这组示例数据，不会自动向你的数据库插入记录。每个查询函数都接收一个 `AsyncSession`，返回 `Book` 实例列表；没有匹配记录时返回 `[]`。

代码中添加 `order_by(Book.id)`，方便按主键顺序观察结果。

## 三、六种基本比较条件

### 1. 等于：==

需求：查询价格等于 30 的书籍。

```python
async def query_equal(db: AsyncSession):
    stmt = select(Book).where(Book.price == 30).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

SQL 条件相当于 `WHERE price = 30`，示例中返回 `id=1`。

Python 的赋值用 `=`，比较用 `==`；所以不能在条件中写 `Book.price = 30`。

等于也能比较字符串，例如：

```python
async def query_publisher(db: AsyncSession):
    stmt = select(Book).where(
        Book.publisher == "XinHua"
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

它按数据库的字符串比较规则进行相等匹配，不是子串匹配，示例返回 `id=1、2`。

### 2. 不等于：!=

需求：查询价格不等于 30 的书籍。

```python
async def query_not_equal(db: AsyncSession):
    stmt = select(Book).where(Book.price != 30).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

SQL 条件相当于 `WHERE price != 30`，示例返回 `id=2、3`。

如果字段允许保存 `NULL`，`!= 30` 不会把空值也选出来。空值应单独判断，见后文。

### 3. 大于：>

需求：查询价格高于 30 的书籍，不包含 30。

```python
async def query_greater(db: AsyncSession):
    stmt = select(Book).where(Book.price > 30).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

SQL 条件相当于 `WHERE price > 30`，示例只返回价格为 50 的 `id=2`。

### 4. 小于：<

需求：查询价格低于 30 的书籍，不包含 30。

```python
async def query_less(db: AsyncSession):
    stmt = select(Book).where(Book.price < 30).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

SQL 条件相当于 `WHERE price < 30`，示例只返回价格为 20 的 `id=3`。

### 5. 大于等于：>=

需求：查询价格不低于 30 的书籍，包含 30。

```python
async def query_greater_equal(db: AsyncSession):
    stmt = select(Book).where(Book.price >= 30).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

SQL 条件相当于 `WHERE price >= 30`，示例返回 `id=1、2`。

与 `> 30` 相比，多出了恰好等于 30 的书。

### 6. 小于等于：<=

需求：查询价格不高于 30 的书籍，包含 30。

```python
async def query_less_equal(db: AsyncSession):
    stmt = select(Book).where(Book.price <= 30).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

SQL 条件相当于 `WHERE price <= 30`，示例返回 `id=1、3`。

与 `< 30` 相比，多出了恰好等于 30 的书。

## 四、组合比较：查询一个价格范围

### 1. where() 传入多个条件

需求：查询价格在 20 到 30 之间的书籍，包含 20 和 30。

```python
async def query_range(db: AsyncSession):
    stmt = select(Book).where(
        Book.price >= 20,
        Book.price <= 30,
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

`where(条件1, 条件2)` 表示两个条件同时满足，对应 `WHERE price >= 20 AND price <= 30`，示例返回 `id=1、3`。

也可以把构造语句的部分写成：

```python
stmt = select(Book).where(Book.price >= 20).where(Book.price <= 30)
```

这里筛选用的是模型类上的 `Book.price`，SQLAlchemy 会把比较转换成 SQL 表达式，交给数据库执行；不是先读取所有书籍再用 Python 逐本判断。

### 2. between() 的简写

```python
async def query_between(db: AsyncSession):
    stmt = select(Book).where(
        Book.price.between(20, 30)
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

对应 `WHERE price BETWEEN 20 AND 30`，同样返回 `id=1、3`。

`between(下限, 上限)` 包含两端。如果希望排除边界，应使用 `Book.price > 20` 和 `Book.price < 30` 两个条件。

不要写 Python 连续比较 `20 <= Book.price <= 30`，也不要用 Python 的 `and` 连接 SQL 条件。若使用 `&`，每个比较条件需要加括号：

```python
stmt = select(Book).where((Book.price >= 20) & (Book.price <= 30))
```

## 五、特殊比较：NULL 空值

### 1. 查询空值：is_(None)

```python
async def query_null(db: AsyncSession):
    stmt = select(Book).where(Book.publisher.is_(None)).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

对应 SQL 的 `WHERE publisher IS NULL`。Python 中用 `None` 表示这里要比较的数据库空值。

### 2. 查询非空值：is_not(None)

```python
async def query_not_null(db: AsyncSession):
    stmt = select(Book).where(Book.publisher.is_not(None)).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

对应 SQL 的 `WHERE publisher IS NOT NULL`。

当前 `Book.publisher` 是非空字段，正常数据中，第一种查询返回 `[]`，第二种返回全部三本书。本节仅说明语法，无需为了演示而修改表结构。

`NULL` 不等于空字符串 `""`，也不等于 `0`。SQLAlchemy 也能将 `Book.publisher == None` 转换为 `IS NULL`，但显式写 `is_(None)` 更容易辨认。不要写 `Book.publisher is None`：Python 的 `is` 不会构造 SQL 条件。

## 六、在路由中接收比较值

前面的数值写在代码里。实际接口通常从查询参数取得上下限：

```python
@app.get("/book/filter")
async def filter_books(
    min_price: float = Query(0, ge=0, description="最低价格，包含此值"),
    max_price: float = Query(100, ge=0, description="最高价格，包含此值"),
    db: AsyncSession = Depends(get_database, scope="function"),
):
    if min_price > max_price:
        raise HTTPException(status_code=400, detail="最低价格不能大于最高价格")

    stmt = select(Book).where(
        Book.price >= min_price,
        Book.price <= max_price,
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

请求 `GET /book/filter?min_price=20&max_price=30`，示例返回 `id=1、3`。

- `Query(0, ge=0)`：默认值为 0，并限制参数不小于 0。
- `Query(100, ge=0)`：默认最高价为 100。
- `min_price > max_price`：这是两个已解析的 Python 数值之间的比较，用来校验参数。
- `Book.price >= min_price`：这是数据库字段与参数之间的比较，用来构造 SQL 条件。

SQLAlchemy 会将比较值作为绑定参数传给数据库。日志中可能看到 `WHERE book.price >= ?`，数值单独传递；不需要自己拼接 SQL 字符串。

参考资料：

- [SQLAlchemy 比较运算符](https://docs.sqlalchemy.org/en/20/core/operators.html#comparison-operators)
- [SQLAlchemy NULL 与身份比较](https://docs.sqlalchemy.org/en/20/core/operators.html#identity-comparisons)
