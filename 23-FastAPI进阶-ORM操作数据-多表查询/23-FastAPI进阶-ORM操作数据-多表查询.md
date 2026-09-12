# 23-FastAPI进阶-ORM操作数据-多表查询

本节按以下顺序学习：**找出关联字段 → 内连接 → 读取结果 → 条件筛选 → 左连接 → 分组统计 → 接入路由**。

## 一、为什么需要多表查询

书籍表 `book` 保存书籍 ID、书名、作者姓名、价格等信息；作者表 `author` 保存作者 ID（主键）、姓名、国籍和简介。

如果接口需要同时返回“书名、作者姓名、作者国籍”，信息就分散在两张表中。**多表查询通过关联条件，把不同表中相互对应的记录组合成查询结果。** 本节使用的 `JOIN`（连接查询）在数据库中完成匹配。

### 1. 先看现有数据

沿用根目录 [database_sqlite.py](../database_sqlite.py) 中的 `Book`、`Author`、`app` 和 `get_database`。两张表已经存放在 `sql/fastapi.db` 中，无须重新建表。

当前数据关系为：

```text
author_id=1，John Doe，美国，对应书籍 id=1、2、3
author_id=2，Kate Smith，英国，对应书籍 id=4
author_id=3，LuoGuanzhong，中国，对应书籍 id=5
author_id=4，张三，中国，对应书籍 id=6
author_id=5，李四，中国，对应书籍 id=7
```

共有 7 本书、5 位作者。国籍和简介是前面填充的测试资料；下文结果以这些数据为例。

### 2. 作者表的主键是 author_id

**作者表已经定义了整数主键 `author_id`，用于唯一标识一位作者。** 它就是作者的 ID，不需要再增加另一列 `id` 作为主键。

`Author` 模型中的定义为：

```python
# 以下是 Author 类内部的字段定义
author_id: Mapped[int] = mapped_column(primary_key=True, comment="作者ID")
```

`Mapped[int]` 表示该属性使用整数，`primary_key=True` 表示主键。在当前 SQLite 表中，插入作者时可以省略这个字段，由数据库生成整数 ID。

例如，可以在异步函数中按主键查询：

```python
author = await db.get(Author, 1)
if author is not None:
    print(author.author_id, author.name)  # 1 John Doe
```

**作者表有主键，与书籍表是否保存作者 ID，是两个不同的问题。** 当前 `Book.author` 保存的是姓名字符串，没有 `Book.author_id` 字段。因此，后面的连接查询仍然按姓名匹配，不能直接把书籍 ID 与作者 ID 相等作为关联条件。

### 3. 明确关联条件

本项目当前按姓名关联：

```python
Book.author == Author.name
```

例如，某本书的 `author` 是 `"John Doe"`，就匹配作者表中 `name` 为 `"John Doe"` 的记录。

注意两点：

- `Book.id` 是书籍 ID，`Author.author_id` 是作者 ID，它们不是本节的关联字段。数字碰巧相同不代表两条记录对应。
- 当前书籍表没有作者 ID 外键，因此示例需要显式写出连接条件，不能指望 `join(Author)` 自动根据字段名猜测关系。

当前导入的作者姓名没有重复，所以每本书最多匹配一条作者记录。姓名字段本身没有唯一约束：将来出现同名作者时，按姓名连接可能把一本书匹配到多位作者。后续可学习在书籍表保存作者 ID，并使用外键关联；本节先掌握现有结构下的连接查询。[显式连接条件](https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html#joins-to-a-target-with-an-on-clause)

### 4. 代码准备

下面的查询函数可以接在已有模型和依赖定义后：

```python
from fastapi import Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
```

每个查询函数接收 `db: AsyncSession`，即用于执行 SQL 的异步会话。构造语句时不访问数据库，`await db.execute(stmt)` 才执行查询；其后的结果读取方法不加 `await`。

## 二、第一步：内连接，查出书名与作者国籍

### 1. 完整查询代码

**内连接（INNER JOIN）只返回两边满足连接条件的记录组合。**

```python
async def query_books_with_authors(db: AsyncSession):
    stmt = (
        select(
            Book.id.label("book_id"),
            Book.bookname,
            Author.name.label("author_name"),
            Author.nationality,
        )
        .select_from(Book)
        .join(Author, Book.author == Author.name)
        .order_by(Book.id)
    )
    result = await db.execute(stmt)
    return [dict(row) for row in result.mappings().all()]
```

对应 SQL：

```sql
SELECT book.id AS book_id, book.bookname,
       author.name AS author_name, author.nationality
FROM book
JOIN author ON book.author = author.name
ORDER BY book.id;
```

### 2. 按步骤理解参数

- `select(...)`：决定返回哪些字段；可以同时选择两张表的字段。
- `label("book_id")`、`label("author_name")`：为结果列命名，方便接口返回，不修改表结构。
- `select_from(Book)`：明确以书籍表作为连接的起点。
- `join(Author, 条件)`：`Author` 是要连接的目标表，第二个参数是 `ON` 条件，用来判断两条记录是否匹配。默认是内连接。
- `order_by(Book.id)`：按书籍 ID 排序，固定结果顺序。
- `mappings().all()`：按字段名读取多行；再将每个 `RowMapping` 转成普通字典。

当前返回 7 行，其中第一行是：

```json
{
  "book_id": 1,
  "bookname": "Python for Beginners",
  "author_name": "John Doe",
  "nationality": "美国"
}
```

John Doe 对应三本书，所以他会出现在三行结果中。**连接结果中的一行表示“一本书与一位匹配作者的组合”，不会自动把他的三本书收集成一个列表。**

如果某本书找不到作者，内连接中就没有这本书的结果。

### 3. 不能只把两个模型放进 select()

`select(Book, Author)` 只是选择两个实体，不会自动知道作者和书籍怎样关联。

如果既没有 `JOIN ON`，也没有其他关联条件，本例可能得到 `7 × 5 = 35` 种组合，即每本书都与每位作者配对。这叫笛卡尔积，并不是我们想要的对应关系。

## 三、第二步：如果选择两个完整模型，怎样读取

上一节选择具体字段，适合组织字典。如果业务需要访问两个模型的属性，也可以选择两个实体：

```python
async def query_book_author_objects(db: AsyncSession):
    stmt = (
        select(Book, Author)
        .select_from(Book)
        .join(Author, Book.author == Author.name)
        .order_by(Book.id)
    )
    result = await db.execute(stmt)
    return result.all()
```

这里每行的形状是：

```text
(Book实例, Author实例)
```

可以在异步函数中这样使用：

```python
rows = await query_book_author_objects(db)
for book, author in rows:
    print(book.bookname, author.name, author.nationality)
```

`for book, author in rows` 将每行的两个元素分别赋给两个变量。

如果改成 `result.scalars().all()`，默认只留下每行第一个元素，也就是 `Book` 实例；`Author` 不会一起出现在返回值中。这个辅助函数的 `Row` 列表用于 Python 内部处理，直接作为接口响应时，应先组织成需要的字典结构。

这里复用了之前的结果读取知识，详见 [SQLAlchemy 查询结果与取值](../00-python基础补充/09-SQLAlchemy查询结果与取值.md)。

## 四、第三步：连接后增加查询条件

需求：查询指定国籍作者的书籍，例如中国作者的书。

```python
async def query_books_by_nationality(
    db: AsyncSession,
    nationality: str,
):
    stmt = (
        select(
            Book.id.label("book_id"),
            Book.bookname,
            Author.name.label("author_name"),
            Author.nationality,
        )
        .select_from(Book)
        .join(Author, Book.author == Author.name)
        .where(Author.nationality == nationality)
        .order_by(Book.id)
    )
    result = await db.execute(stmt)
    return [dict(row) for row in result.mappings().all()]
```

`nationality` 是普通字符串参数，传入 `"中国"` 时返回书籍 `id=5、6、7`；传入没有匹配作者的国籍时返回 `[]`。

本例中：

- `ON book.author = author.name` 说明书籍和作者如何配对。
- `WHERE author.nationality = ...` 说明要保留哪些配对结果。

之前学习的价格比较、书名模糊查询等条件同样可用，例如在 `where()` 中同时放入 `Book.price >= 50` 和国籍条件。

## 五、第四步：左连接，保留找不到作者的书籍

### 1. 左连接与内连接有什么不同

**左外连接（LEFT OUTER JOIN，简称左连接）保留左表的记录。** 如果右表找不到匹配记录，结果中右表的字段用 SQL `NULL` 补齐，在 Python 中表现为 `None`。

需求改为：“所有书都要展示，能找到作者资料就附带展示。”

```python
async def query_books_left_join(db: AsyncSession):
    stmt = (
        select(
            Book.id.label("book_id"),
            Book.bookname,
            Author.name.label("author_name"),
            Author.nationality,
        )
        .select_from(Book)
        .outerjoin(Author, Book.author == Author.name)
        .order_by(Book.id)
    )
    result = await db.execute(stmt)
    return [dict(row) for row in result.mappings().all()]
```

这里 `Book` 是左侧起点，`Author` 是右侧目标，`outerjoin(...)` 默认生成左外连接。也可以把这一行改成 `.join(Author, Book.author == Author.name, isouter=True)`。

`isouter=True` 表示使用外连接；本例就是保留左侧书籍的左连接。[SQLAlchemy 外连接说明](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html#outer-and-full-join)

### 2. 为什么当前看起来和内连接一样

目前每本书都能匹配到作者，所以两个查询都返回 7 行。**结果相同，是因为当前没有缺少匹配的数据，不代表连接方式相同。**

假设将来新增一本书，`Book.author` 为 `"尚未录入的作者"`，作者表却没有这个姓名：

- 内连接：这本书不出现在结果中。
- 左连接：保留这本书，`author_name` 和 `nationality` 为 `None`，返回 JSON 时为 `null`。

这是查询结果中的空值，不是把作者表的国籍改成了 `NULL`，也不违反作者表已有的 `NOT NULL` 约束。

如果左连接选择的是 `select(Book, Author)`，这本书对应的行则是 `(Book实例, None)`，读取前要判断作者是否存在。

## 六、第五步：理解左连接中 ON 与 WHERE 的位置

这一节只改变一个要求：**所有书籍都保留，但只附带中国作者的资料。**

```python
async def query_books_with_chinese_author_info(db: AsyncSession):
    stmt = (
        select(
            Book.id.label("book_id"),
            Book.bookname,
            Author.name.label("author_name"),
            Author.nationality,
        )
        .select_from(Book)
        .outerjoin(
            Author,
            and_(
                Book.author == Author.name,
                Author.nationality == "中国",
            ),
        )
        .order_by(Book.id)
    )
    result = await db.execute(stmt)
    return [dict(row) for row in result.mappings().all()]
```

`and_(...)` 把两个条件用 SQL 的 `AND` 连接。放进 `ON` 后，右侧作者必须同时满足“姓名匹配”和“国籍是中国”，才附带到书籍上。

当前仍然返回 **7 本书**：

- `id=5、6、7`：附带中国作者资料。
- `id=1、2、3、4`：书籍保留，作者字段为 `None`。这些作者实际存在，只是没有满足本次 `ON` 条件。

如果改成下面的写法，结果就不同了：

```python
stmt = (
    select(Book.id, Author.nationality)
    .select_from(Book)
    .outerjoin(Author, Book.author == Author.name)
    .where(Author.nationality == "中国")
    .order_by(Book.id)
)
```

它先按姓名左连接，再用 `WHERE` 筛选结果，只剩 **3 本书，即 id=5、6、7**。国籍为美国、英国或补出的 `NULL` 的行都无法通过该条件。

所以，**左连接之后追加条件，不一定还能保留所有左表记录。** 对这个例子，“只匹配中国作者资料”放在 `ON`，“只返回中国作者的书”放在 `WHERE`，表达的是两个不同需求。

## 七、第六步：结合分组，统计每位作者的书籍数量

现在改变查询起点：希望每位作者都有一行统计，即使没有书也显示数量 `0`。因此以 `Author` 为左侧起点，左连接 `Book`。

```python
async def query_author_book_counts(db: AsyncSession):
    stmt = (
        select(
            Author.author_id,
            Author.name,
            func.count(Book.id).label("book_count"),
        )
        .select_from(Author)
        .outerjoin(Book, Author.name == Book.author)
        .group_by(Author.author_id, Author.name)
        .order_by(Author.author_id)
    )
    result = await db.execute(stmt)
    return [dict(row) for row in result.mappings().all()]
```

当前返回 5 行：

```json
[
  {"author_id": 1, "name": "John Doe", "book_count": 3},
  {"author_id": 2, "name": "Kate Smith", "book_count": 1},
  {"author_id": 3, "name": "LuoGuanzhong", "book_count": 1},
  {"author_id": 4, "name": "张三", "book_count": 1},
  {"author_id": 5, "name": "李四", "book_count": 1}
]
```

这里分三步理解：

1. `select_from(Author)` 决定保留作者。
2. `outerjoin(Book, ...)` 找出每位作者对应的书籍。
3. `group_by(...)` 将同一作者的连接结果归为一组，`count(Book.id)` 统计匹配的书籍数。

**为什么用 `count(Book.id)`，而不是 `count()`？**

假设一位作者没有任何书，左连接仍保留一行，只是其中 `Book.id` 为 `NULL`：

- `COUNT(book.id)` 忽略 `NULL`，得到正确的 `0`。
- `COUNT(*)` 统计连接后的行数，连这条补空行也会计算，得到 `1`。

如果要只保留书籍数大于一本的作者，可以继续追加 `.having(func.count(Book.id) > 1)`，当前只剩 John Doe。这是筛选统计结果，所以仍使用上一节学习的 `having()`。

## 八、第七步：把查询函数接入 FastAPI

添加下面两个路由，调用前面的查询函数：

```python
@app.get("/book/with-authors")
async def get_books_with_authors(
    nationality: str | None = Query(
        None, min_length=1, description="作者国籍，不传则查询全部匹配记录"
    ),
    db: AsyncSession = Depends(get_database),
):
    if nationality is None:
        return await query_books_with_authors(db)
    return await query_books_by_nationality(db, nationality)


@app.get("/author/book-counts")
async def get_author_book_counts(
    db: AsyncSession = Depends(get_database),
):
    return await query_author_book_counts(db)
```

参数解释：

- `nationality: str | None`：可以是国籍字符串，也可以是 `None`。
- `Query(None, min_length=1, ...)`：从查询参数读取国籍；不传时为 `None`，传入空字符串会校验失败。
- `Depends(get_database)`：让 FastAPI 获取数据库会话并赋给 `db`。
- `await query_...(db)`：调用异步查询函数，取得普通字典列表后交给 FastAPI 返回 JSON。

把函数与路由添加到根目录脚本后，在项目根目录启动：

```bash
uv run fastapi dev database_sqlite.py
```

可以在 `/docs` 中测试：

- `GET /book/with-authors`：返回 7 条书籍与作者的匹配记录。
- `GET /book/with-authors?nationality=中国`：返回 3 条记录。
- `GET /author/book-counts`：返回 5 位作者的书籍数量。

本节查询不会修改书籍或作者资料。先熟悉显式连接条件、结果形状以及内连接和左连接的差别，再继续学习外键、`relationship()` 和关系加载。
