# 20-FastAPI进阶-ORM操作数据-模糊查询与逻辑条件

本节继续学习比较判断以外的常见条件：字符串匹配、与／或／非组合、集合包含和存在性判断。

沿用 `Book`、`app`、`get_database`。查询函数可以接在模型和依赖定义之后，使用以下导入：

```python
from fastapi import Depends, Query
from sqlalchemy import and_, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
```

所有示例均在数据库中筛选，不需要先把全部数据取回 Python。查询函数返回 `Book` 实例列表，没有匹配数据时返回 `[]`；存在性查询则返回布尔值。

为说明结果，假设有四本书：

```text
id=1，书名="Python for Beginners"，作者="John Doe"，价格=30，出版社="XinHua"
id=2，书名="FastAPI Guide"，作者="Jane Doe"，价格=50，出版社="XinHua"
id=3，书名="SQL Basics"，作者="John Doe"，价格=20，出版社="TechPress"
id=4，书名="Python Practice"，作者="John Doe"，价格=60，出版社="TechPress"
```

以上是说明数据，不会自动插入数据库。代码中的 `order_by(Book.id)` 用于固定结果顺序。

## 一、模糊查询

### 1. like()：按照通配模式匹配

`like()` 接收一个匹配模式，对应 SQL 的 `LIKE`：

- `%`：匹配零个或多个字符。
- `_`：匹配恰好一个字符。
- 其他字符：按数据库的匹配规则比较。

例如，查询书名包含 Python 的书：

```python
async def query_like(db: AsyncSession):
    stmt = select(Book).where(
        Book.bookname.like("%Python%")
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

SQL 条件类似 `WHERE bookname LIKE '%Python%'`，示例返回 `id=1、4`。

其他模式可以这样写：

```python
# 以 Python 开头：id=1、4
stmt = select(Book).where(Book.bookname.like("Python%"))

# 以 Guide 结尾：id=2
stmt = select(Book).where(Book.bookname.like("%Guide"))

# SQL 与 Basics 之间恰好有一个字符：id=3，中间的空格匹配 _
stmt = select(Book).where(Book.bookname.like("SQL_Basics"))
```

这些是替换条件的片段，执行时仍使用 `await db.execute(stmt)` 和 `result.scalars().all()`。

### 2. ilike()：表达忽略大小写的匹配意图

```python
async def query_ilike(db: AsyncSession):
    stmt = select(Book).where(
        Book.bookname.ilike("%python%")
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

示例返回 `id=1、4`。SQLAlchemy 在 SQLite 上通常将它转换为类似 `lower(bookname) LIKE lower(?)`；在支持 `ILIKE` 的数据库上可以使用原生运算符。

不能简单地认为“`like()` 一定区分大小写”。SQLite 默认的 `LIKE` 对 ASCII 英文字母就不区分大小写，所以本例使用 `like("%python%")` 也可能得到相同结果。非 ASCII 字符的大小写匹配能力取决于数据库及其配置，`ilike()` 不保证自动解决所有语言的大小写转换。[SQLite 的 LIKE 规则](https://www.sqlite.org/lang_expr.html#like)。

### 3. not_like()：排除匹配模式的记录

```python
async def query_not_like(db: AsyncSession):
    stmt = select(Book).where(
        Book.bookname.not_like("%Python%")
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

对应 `NOT LIKE`，示例返回 `id=2、3`。也可以写成 `~Book.bookname.like("%Python%")`。

### 4. contains()：查询包含某段文本

```python
async def query_contains(db: AsyncSession, keyword: str):
    stmt = select(Book).where(
        Book.bookname.contains(keyword, autoescape=True)
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

传入 `"Python"` 时返回 `id=1、4`。`contains()` 会组织“任意前缀 + 文本 + 任意后缀”的匹配，不必自己加两侧的 `%`。

`autoescape=True` 表示将输入中的 `%`、`_` 等匹配特殊字符作为普通文本处理。例如搜索 `"100%"` 时，要求书名确实包含 `100%`，而不是匹配所有以 `100` 开头的片段。

要区分：

- `like(f"%{keyword}%")`：输入中的 `%`、`_` 会参与通配匹配。
- `contains(keyword, autoescape=True)`：输入按普通文本进行包含查询。

两种写法的值都会通过 SQLAlchemy 参数绑定传递；`autoescape` 处理的是通配符含义，不是把原始 SQL 拼接变安全的工具。

### 5. startswith() 和 endswith()：开头与结尾

```python
async def query_startswith(db: AsyncSession):
    stmt = select(Book).where(
        Book.bookname.startswith("Python", autoescape=True)
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()


async def query_endswith(db: AsyncSession):
    stmt = select(Book).where(
        Book.bookname.endswith("Guide", autoescape=True)
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

`startswith("Python")` 匹配书名开头，返回 `id=1、4`；`endswith("Guide")` 匹配书名结尾，返回 `id=2`。它们通常也转换为 `LIKE` 形式，大小写规则不等同于 Python 字符串同名方法。

## 二、与、或、非查询

这里的“与、或、非”是把多个 SQL 条件组合起来。本节也单独给出严格意义上的“与非”示例，即 `NOT (A AND B)`。

### 1. 与：and_() 或 &

需求：出版社为 XinHua，并且作者为 John Doe。

```python
async def query_and(db: AsyncSession):
    stmt = select(Book).where(
        and_(Book.publisher == "XinHua", Book.author == "John Doe")
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

两个条件必须同时成立，示例只返回 `id=1`。

下面两种构造语句的写法与它等价：

```python
stmt = select(Book).where(
    Book.publisher == "XinHua",
    Book.author == "John Doe",
)

stmt = select(Book).where(
    (Book.publisher == "XinHua") & (Book.author == "John Doe")
)
```

`where()` 内多个条件默认用 `AND` 连接。

### 2. 或：or_() 或 |

需求：作者为 Jane Doe，或者出版社为 TechPress。

```python
async def query_or(db: AsyncSession):
    stmt = select(Book).where(
        or_(Book.author == "Jane Doe", Book.publisher == "TechPress")
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

满足任意一个条件即可，示例返回 `id=2、3、4`。

等价的符号写法：

```python
stmt = select(Book).where(
    (Book.author == "Jane Doe") | (Book.publisher == "TechPress")
)
```

### 3. 非：not_() 或 ~

需求：排除 XinHua 出版社的书。

```python
async def query_not(db: AsyncSession):
    stmt = select(Book).where(
        not_(Book.publisher == "XinHua")
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

示例返回 `id=3、4`。也可以写 `~(Book.publisher == "XinHua")`；SQLAlchemy 可能将它简化为 `publisher != ?`，不一定在日志中保留 `NOT` 字样。

`~` 作用于 SQLAlchemy 条件表达式时表示 SQL 逻辑取反。不要直接把它当作 Python 布尔值的 `not` 使用。

### 4. 组合条件：先或，再与

需求：书名包含 Python 或 FastAPI，并且出版社为 XinHua。

```python
async def query_combined(db: AsyncSession):
    stmt = select(Book).where(
        and_(
            or_(
                Book.bookname.contains("Python", autoescape=True),
                Book.bookname.contains("FastAPI", autoescape=True),
            ),
            Book.publisher == "XinHua",
        )
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

逻辑为 `(包含 Python OR 包含 FastAPI) AND 出版社为 XinHua`，示例返回 `id=1、2`。

使用 `&`、`|` 组合时应显式加括号，因为它们的 Python 运算优先级可能与直觉不同。不要用 Python 的 `and`、`or`、`not` 代替它们；这些关键字会尝试在 Python 中判断条件，无法正确构造相应的 SQL 组合。

### 5. 与非：不同时满足两个条件

需求：排除“出版社为 XinHua 且作者为 John Doe”的书。

```python
async def query_nand(db: AsyncSession):
    stmt = select(Book).where(
        not_(and_(Book.publisher == "XinHua", Book.author == "John Doe"))
    ).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

只有 `id=1` 同时满足这两个条件，所以被排除，结果为 `id=2、3、4`。

`NOT (A AND B)` 不等于 `(NOT A) AND (NOT B)`：前者只要求不能同时满足，后者要求两个条件都不满足。

## 三、包含查询：值属于某个集合

### 1. in_()：属于指定集合

```python
async def query_in(db: AsyncSession, book_ids: list[int]):
    stmt = select(Book).where(Book.id.in_(book_ids)).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

传入 `[1, 3]` 时，条件类似 `WHERE id IN (1, 3)`，返回 `id=1、3`。也可以查询字符串集合，例如 `Book.publisher.in_(["XinHua", "TechPress"])`。

`in_()` 判断的是字段的**完整值是否属于集合**；`contains()` 判断的是**一个字符串里是否包含一段文本**，两者含义不同。

### 2. not_in()：不属于指定集合

```python
async def query_not_in(db: AsyncSession, book_ids: list[int]):
    stmt = select(Book).where(Book.id.not_in(book_ids)).order_by(Book.id)
    result = await db.execute(stmt)
    return result.scalars().all()
```

传入 `[1, 3]` 时返回 `id=2、4`。等价条件是 `~Book.id.in_(book_ids)`。

不要写 `Book.id in book_ids` 或 `Book.id not in book_ids`，它们是 Python 集合判断，不会生成所需的 SQL `IN` 条件。

### 3. 空集合与 NULL

- `Book.id.in_([])`：没有任何主键属于空集合，返回空列表。
- `Book.id.not_in([])`：不排除任何主键，本例返回全部书籍。
- 排除列表中不要随意混入 `None`。例如 `NOT IN (1, NULL)` 会受到 SQL 空值逻辑影响，可能一条也查不到。

本例 `publisher` 是非空字段。如果其他模型的字段允许为空，`NOT LIKE`、`!=`、`NOT IN` 通常不会自动选出空值；需要包括空值时，要显式用 `or_(原条件, 字段.is_(None))` 组合。具体空值语法见[第 19 节](../19-FastAPI进阶-ORM操作数据-条件查询/19-FastAPI进阶-ORM操作数据-条件查询.md)。

## 四、补充：是否存在匹配记录

只想知道“有没有”，不需要读取全部 ORM 对象时，可以用 `EXISTS`：

```python
async def has_matching_book(db: AsyncSession, keyword: str):
    condition = select(Book.id).where(
        Book.bookname.contains(keyword, autoescape=True)
    ).exists()
    result = await db.execute(select(condition))
    return result.scalar_one()
```

传入 `"Python"` 得到 `True`，传入 `"不存在的书名"` 得到 `False`。

`.exists()` 将查询转换为存在性表达式；外层 `select(condition)` 取得这个判断结果。这里 `scalar_one()` 返回布尔值，而不是 `Book` 对象。

## 五、综合路由：按关键词、出版社与排除主键筛选

沿用已有 `app` 和 `get_database`：

```python
@app.get("/book/search")
async def search_books(
    keyword: str | None = Query(None, min_length=1, description="书名包含的普通文本"),
    publishers: list[str] | None = Query(None, description="允许的出版社，可重复传入"),
    exclude_ids: list[int] | None = Query(None, description="需要排除的书籍主键"),
    db: AsyncSession = Depends(get_database, scope="function"),
):
    stmt = select(Book)

    if keyword is not None:
        stmt = stmt.where(Book.bookname.contains(keyword, autoescape=True))

    if publishers is not None:
        stmt = stmt.where(Book.publisher.in_(publishers))

    if exclude_ids is not None:
        stmt = stmt.where(Book.id.not_in(exclude_ids))

    result = await db.execute(stmt.order_by(Book.id))
    return result.scalars().all()
```

调用示例：

- `GET /book/search?keyword=Python`：返回 `id=1、4`。
- `GET /book/search?publishers=XinHua&publishers=TechPress`：列表参数通过重复参数名传入，返回四本书。
- `GET /book/search?keyword=Python&publishers=XinHua`：同时满足关键词和出版社，返回 `id=1`。
- `GET /book/search?keyword=Python&exclude_ids=1`：排除主键 1，返回 `id=4`。

`Query(None)` 表示参数可省略；`min_length=1` 限制传入的关键词至少一个字符。多次调用 `where()` 会将筛选条件以 `AND` 累加。

这里的 `if keyword is not None` 是对已经解析的 Python 参数做判断；`Book.publisher.in_(publishers)` 才是在构造数据库条件。没有传入筛选参数时，本例查询全部书籍；数据较多时可结合第 18 节的分页。

参考资料：

- [SQLAlchemy 字符串匹配](https://docs.sqlalchemy.org/en/20/core/operators.html#string-comparisons)
- [SQLAlchemy 逻辑组合](https://docs.sqlalchemy.org/en/20/core/operators.html#using-conjunctions-and-negations)
- [SQLAlchemy 集合包含](https://docs.sqlalchemy.org/en/20/core/operators.html#in-comparisons)
