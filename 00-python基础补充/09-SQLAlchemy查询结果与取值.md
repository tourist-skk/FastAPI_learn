# 09-SQLAlchemy查询结果与取值

这些名字不能平铺着记。理解它们需要分清三个问题：

1. **执行层：结果从哪里来、经过什么处理？** 对应 `CursorResult`、`IteratorResult`、`ChunkedIteratorResult`。
2. **读取层：每次要取整行、一个元素，还是按名称取字段？** 对应 `Result`、`ScalarResult`、`MappingResult` 的读取方式。
3. **异步层：读取结果时是否还需要等待？** 对应普通结果与 `AsyncResult` 等异步结果。

本文先建立类型关系，再解释 `execute()` 的内部选择流程，最后按“共同方法 → 各类型特有方法”学习。ORM 实例本身见 [08-ORM对象](08-ORM对象.md)。

## 一、示例准备

沿用项目中的 `Book` 模型、异步引擎 `engine` 和 `AsyncSession` 会话 `db`：

```python
from sqlalchemy import func, select, text
from sqlalchemy.engine import Result
```

含 `await` 的片段放在异步函数内执行。各示例独立查询；以下输出基于三条说明数据，不会自动插入数据库：

```text
id=1，bookname="Python for Beginners"，author="John Doe"，price=30，publisher="XinHua"
id=2，bookname="FastAPI Guide"，author="Jane Doe"，price=50，publisher="XinHua"
id=3，bookname="SQL Basics"，author="John Doe"，price=20，publisher="TechPress"
```

源码流程与具体类型输出以本项目安装的 **SQLAlchemy 2.0.52 + SQLite + aiosqlite** 为准；公共读取方法与内部实现细节会分别说明。

## 二、先建立类型关系

### 1. Result 及其子类：结果的具体实现

简化的继承关系：

```text
Result：提供统一的按行读取接口
├── CursorResult：包装数据库驱动的游标结果
└── IteratorResult：以 Python 迭代器作为结果来源
    └── ChunkedIteratorResult：以能提供批次的函数作为结果来源
```

`CursorResult` 和 `ChunkedIteratorResult` **都属于 `Result`**，因此都能调用 `all()`、`scalar()`、`scalars()`、`mappings()` 等公共方法。主要差别在数据来源和内部处理，不是各自需要一套完全不同的取值方法。

```python
result = await db.execute(select(Book))
print(type(result).__name__)       # ChunkedIteratorResult：具体类
print(isinstance(result, Result))  # True：也是 Result 的实例
result.close()
```

“返回 `Result`”是对公共接口的描述；打印时看到子类名并不矛盾。

### 2. ScalarResult 与 MappingResult：包装已有结果的读取视图

另一组简化继承关系：

```text
FilterResult
├── ScalarResult：每行取一个元素
└── MappingResult：每行按键和值读取
```

它们不是 `Result` 的子类，而是**持有并包装已有 `Result`**。这里的过滤是改变读取形状，不是 SQL 的 `WHERE` 行筛选，也不会重新执行 SQL。

假设数据库返回的结果包含：

```text
(1, "Python for Beginners")
(2, "FastAPI Guide")
(3, "SQL Basics")
```

同一份结果，用三种方式读，得到的「每行形状」不同： 

- `result.all()`：`Row` 列表，每行保留两个元素。`[(1, "Python..."), (2, "FastAPI..."), ...]`
- `result.scalars().all()`：`[1, 2, 3]`，默认每行只取第一列。
- `result.mappings().all()`：`RowMapping` 列表，每行类似 `[{"id": 1, "bookname": "Python..."}, ...]`

这三种是对**分别重新执行的查询结果**进行比较，不能对同一结果连续读取三遍。
因为:Result 是会被消耗的（文档第七节专门讲了这个）。
scalars() 和 mappings() 不会复制原结果，它们和原 result 共享同一个读取进度。如果你对同一个结果连续读三遍，第一次 all() 就把数据全读光了，后面两次只会拿到空列表：

### 3. 为什么已有 Result，还要提供这两个视图

**适用场景不同，而这种设计把“执行查询”和“选择读取形状”分开了。** `Result` 提供通用的行结构，`ScalarResult` 和 `MappingResult` 让业务代码明确选择怎样读取这些行。

仅使用 `Result` 也能完成取值。例如，同样查询 ID 和书名，只需要 ID 时，可以自己提取，也可以使用 `ScalarResult`：

```python
stmt = select(Book.id, Book.bookname).order_by(Book.id)

# 使用 Result：自己从每行取出第一个元素
result = await db.execute(stmt)
ids = [row[0] for row in result.all()]

# 使用 ScalarResult：把“每行只取一个元素”交给读取视图
result = await db.execute(stmt)
ids = result.scalars().all()
# 两种写法都得到 [1, 2, 3]
```

`ScalarResult` 的作用不只是省去一次列表推导式：它让后续的 `all()`、`first()`、`one()`、迭代等操作，都按“单个元素”读取。适合需要书籍对象列表、ID 列表或书名列表的场景。

如果需要保留多个字段，并通过字段名读取，可以选择 `MappingResult`：

```python
result = await db.execute(
    select(Book.id, Book.bookname).order_by(Book.id)
)
rows = result.mappings().all()

for row in rows:
    print(row["id"], row["bookname"])

items = [dict(row) for row in rows]  # 组织为普通字典列表
```

这种方式适合多字段查询和组织接口返回值，不必记住每个字段位于第几列。

**为什么不让 Result 自动决定？** 同一个 `select(Book.id, Book.bookname)`，调用者可能需要整行、仅 ID，或者按名称访问的字段映射。查询语句说明“查什么”，但不能完全说明“调用者打算怎样使用结果”。因此，由调用者通过 `scalars()` 或 `mappings()` 明确选择。

使用独立类型，也使每个类型的返回规则保持清晰：`Result.all()` 返回行，`ScalarResult.all()` 返回单个元素，`MappingResult.all()` 返回行映射，便于阅读代码和类型检查。这是 API 的设计选择，不是数据库要求必须建立三个结果类。

建立这两个视图不会再次查询，也不会复制整批数据；它们仍共享原结果的读取进度。[SQLAlchemy 结果视图说明](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Result.mappings)

### 4. 单行、单个值和结果容器不是一回事

- `Result`、`ScalarResult`、`MappingResult`：负责读取一批结果。
- `Row`：一行，支持 `row[0]`，列名合适时也可以用 `row.id`。
- `RowMapping`：一行的只读映射，支持 `row["id"]`。
- `Book`、`int`、`str`、`None`：行里的某个元素。
- `list`、`dict`：收集或转换之后得到的普通 Python 容器。

`select(Book)` 的 ORM 结果中，每行形如 `(Book实例,)`；`select(Book.id, Book.bookname)` 中，每行才是 `(整数, 字符串)`。**选择什么决定行里有什么，读取方法决定怎样取出来。**

## 三、execute() 为什么会返回不同的实现类

### 1. 首先看调用者：Session 还是 Connection

`db` 只是变量名。项目中的 `db` 是 `AsyncSession`，它在执行 SQL 之外还负责 ORM 对象的加载与会话管理。

`AsyncConnection` 是数据库连接，主要负责执行 SQL。即使给它传入 `select(Book)`，也不会像 ORM 会话一样把字段组装为 `Book` 实例：

```python
# 会话：执行 ORM 查询，加载模型实例
result = await db.execute(select(Book).order_by(Book.id))
print(type(result).__name__)  # ChunkedIteratorResult
book = result.scalars().first()
print(book.bookname)         # Python for Beginners

# 连接：得到字段组成的行
async with engine.connect() as connection:
    result = await connection.execute(select(Book).order_by(Book.id))
    print(type(result).__name__)  # CursorResult
    row = result.first()
    print(row.bookname)           # Python for Beginners
```

所以，“同样叫 `execute()`”不意味着调用的是同一个类的方法。

### 2. 对 Session 而言，再看语句是否携带 ORM 信息

构造 `select(Book)`、`select(Book.id)` 等语句时，SQLAlchemy 会把映射类、映射属性携带的 ORM 信息传播到语句上。

当前版本中，`Session._execute_internal()` 的一个关键判断是读取：

```text
statement._propagate_attrs.get("compile_state_plugin") == "orm"
```

这是检查**语句对象上的元数据**，不是扫描 SQL 字符串，也不是等查询完成后再检查返回了几行。

可以用下面的代码观察。下划线属性仅用于本节理解源码，业务代码不需要访问或修改它：

```python
statements = [
    select(Book),
    select(Book.id),
    select(func.count(Book.id)),
    select(Book.__table__),
    text("SELECT id, bookname FROM book"),
]

for stmt in statements:
    result = await db.execute(stmt)
    print(
        stmt._propagate_attrs.get("compile_state_plugin"),
        type(result).__name__,
    )
    result.close()
```

当前环境输出：

```text
orm   ChunkedIteratorResult
orm   ChunkedIteratorResult
orm   ChunkedIteratorResult
None  CursorResult
None  CursorResult
```

`Book.__table__` 是 Core 的 `Table` 表对象；普通 `text(...)` 是文本 SQL。上述两种语句没有走相同的 ORM 结果加载流程。

这也解释了：**只查一个整数，甚至只查一个聚合值，仍然可能返回 `ChunkedIteratorResult`**。返回容器类型取决于执行路径，不取决于最终元素是否为 `Book`。[Session 2.0.52 源码](https://github.com/sqlalchemy/sqlalchemy/blob/rel_2_0_52/lib/sqlalchemy/orm/session.py)

### 3. 两条路径最终怎样生成结果

普通 SELECT 的主要流程可以理解为：

```text
await AsyncSession.execute(stmt)
    ↓
通过异步适配调用内部 Session.execute(stmt)
    ↓
Session 检查语句的 ORM 编译信息
    ├── 普通 Core / text 语句
    │      ↓
    │   Connection.execute(stmt)
    │      ↓
    │   返回 CursorResult
    │
    └── 普通 ORM SELECT
           ↓
        Connection.execute(stmt)
           ↓
        先得到 CursorResult
           ↓
        ORM 处理字段、加载模型实例或提取所选字段
           ↓
        返回 ChunkedIteratorResult
```

关键点是：**ORM 路径也会先执行底层 SQL，再对游标结果做 ORM 处理。**

源码中，普通 ORM SELECT 的 `orm_setup_cursor_result()` 会调用 `loading.instances()`。后者构建每个所选元素的处理函数，并创建 `ChunkedIteratorResult`：选择 `Book` 时加载实例，选择 `Book.id` 时处理字段值。

其内部 `chunks` 函数可以提供一批批处理后的数据；这不是自动发送多条分页 SQL。在当前普通异步 `execute()` 路径中，预缓冲选项 `prebuffer_rows=True` 会提前处理结果，所以类名含 `Chunked` 也不代表正在按需从数据库流式读取。[ORM loading 2.0.52 源码](https://github.com/sqlalchemy/sqlalchemy/blob/rel_2_0_52/lib/sqlalchemy/orm/loading.py)

上图省略了事务、自动刷新和事件等步骤，描述的是本节的普通查询。增删改、`RETURNING`、特殊查询和执行事件可能使用其他结果处理路径，因此不要把“有 ORM 标记就永远返回某个固定类”当作公共 API 保证。

### 4. AsyncSession.execute() 为什么不返回 AsyncResult

`AsyncSession.execute()` 的公共约定是：**异步执行，返回缓冲式 `Result`**。内部通过 `greenlet_spawn` 衔接 SQLAlchemy 的同步实现与异步驱动，不是把整段 ORM 代码放进线程池。

等 `await db.execute(stmt)` 完成后，本节的结果使用普通方法读取：

```python
result = await db.execute(select(Book))
books = result.scalars().all()  # 不加 await
```

`AsyncResult` 是 `await db.stream(stmt)` 使用的异步流式读取包装，见第六节。它不是 `execute()` 因为查到很多行而自动切换出的类型。[AsyncSession.execute()](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.AsyncSession.execute)

## 四、共同方法：同名方法遵守相近规则，但元素形状不同

本节比较 `Result`、`ScalarResult`、`MappingResult`。对它们使用同名读取方法时，先确定每个“元素”是什么：

- `Result`：一个元素是一行 `Row`。
- `ScalarResult`：一个元素是行里选出的值或模型实例。
- `MappingResult`：一个元素是一行 `RowMapping`。

### 1. all()、fetchall()：读取全部剩余元素

三者都有 `all()`，`fetchall()` 是它的同义方法。返回列表，没有剩余结果时返回 `[]`。

```python
stmt = select(Book.id, Book.bookname).order_by(Book.id)

result = await db.execute(stmt)
rows = result.all()
print(rows[0][0], rows[0][1])  # 1 Python for Beginners

result = await db.execute(stmt)
ids = result.scalars().all()
print(ids)                   # [1, 2, 3]

result = await db.execute(stmt)
rows = result.mappings().all()
print(dict(rows[0]))          # {"id": 1, "bookname": "Python for Beginners"}
```

### 2. first()、one()、one_or_none()：读取单个元素

这三个方法在三种结果中都有，区别在于**允许多少个结果元素**：

- `first()`：有结果就取第一个，零个返回 `None`；不检查是否还有其他结果，并关闭结果集、丢弃剩余项。不会自动添加 SQL 的 `LIMIT 1`。
- `one()`：必须恰好一个；零个抛 `NoResultFound`，多个抛 `MultipleResultsFound`。
- `one_or_none()`：允许零个或一个；零个返回 `None`，多个抛 `MultipleResultsFound`。

```python
stmt = select(Book.id, Book.bookname).where(Book.id == 1)

result = await db.execute(stmt)
row = result.one()                  # Row：保留 id、bookname
print(row.bookname)

result = await db.execute(stmt)
book_id = result.scalars().one()    # int：只取 id
print(book_id)                      # 1

result = await db.execute(stmt)
row = result.mappings().one()       # RowMapping：保留两个字段
print(row["bookname"])
```

所以 `one()` 不是固定返回 ORM 对象。它取出的形状由调用它的结果类型决定。

### 3. 迭代、fetchmany(n)、partitions(n)：继续读取剩余结果

三者都可以使用普通 `for`、`next()`、`fetchmany(n)` 和 `partitions(n)`：

- `next(结果)`：取下一个元素；没有更多时抛 `StopIteration`，也可传入默认值。
- `fetchmany(n)`：从当前位置取最多 `n` 个元素组成列表；读完返回 `[]`。
- `partitions(n)`：返回批次迭代器，每批最多 `n` 个元素。

```python
result = await db.execute(select(Book.id).order_by(Book.id))
values = result.scalars()
print(next(values))         # 1
print(values.fetchmany(2))  # [2, 3]
print(values.fetchmany(2))  # []

result = await db.execute(select(Book.id).order_by(Book.id))
for batch in result.mappings().partitions(2):
    print([row["id"] for row in batch])
# [1, 2]
# [3]
```

这些方法划分读取批次，不会自动生成 `offset()`、`limit()` 分页，也不能让已缓冲的结果恢复成数据库流式查询。

### 4. unique()、yield_per()、close()：结果处理与管理

三者都有：

- `unique()`：在 Python 结果读取层去重，不会向 SQL 添加 `DISTINCT`。单字段按值去重；ORM 实体使用 ORM 对应的唯一性策略。
- `yield_per(n)`：配置底层结果的分批读取缓冲策略，实际效果依赖执行方式；不同于 SQL 分页，也不同于一次取出一个批次的 `fetchmany(n)`。
- `close()`：关闭结果，后续读取通常抛 `ResourceClosedError`。`closed` 是查看是否显式／硬关闭的属性，不是统计是否还有剩余数据的方法。

```python
result = await db.execute(select(Book.author).order_by(Book.id))
authors = result.scalars().unique().all()
print(authors)  # ["John Doe", "Jane Doe"]
```

`unique()` 的去重对象随读取形状变化：只取作者时，相同作者合并；保留 `id` 和作者整行时，不同 ID 的行仍然不同。使用 `unique()` 后，`one()` 等方法判断的是去重后的结果。

上述规则适用于本节普通结果；方法的正式定义见 [SQLAlchemy Result Set API](https://docs.sqlalchemy.org/en/20/core/connections.html#result-set-api)。

## 五、各类型还提供什么方法，有什么限制

### 1. Result：在公共方法之外，提供行与取值视图操作

前述共同方法全部可用。此外：

- `fetchone()`：读取下一行 `Row`，读完返回 `None`；不会像 `first()` 那样丢弃剩余行。
- `keys()`：查看结果列名，不读取数据行。
- `columns(...)`：在已有结果中调整读取列的选择与顺序，不修改已执行的 SQL。
- `scalar()`：取第一行的第一个元素，然后关闭结果集。
- `scalar_one()`：相当于 `scalars().one()`。
- `scalar_one_or_none()`：相当于 `scalars().one_or_none()`。
- `scalars(index=0)`：创建 `ScalarResult`，指定每行取哪个位置的元素。
- `mappings()`：创建 `MappingResult`。
- `tuples()`／`t`：提供元组形式的类型标注视图；运行时仍是 `Row`，不是把每行变成普通 `tuple`。
- `freeze()`：消耗剩余结果并保存，得到可重新生成结果的 `FrozenResult`。
- `merge(...)`：合并结构兼容的结果，得到 `MergedResult`。

**重点理解 scalar()：它不是“返回一个数字”，而是“返回一个元素”。**

```python
result = await db.execute(select(Book).order_by(Book.id).limit(1))
book = result.scalar()  # 第一行是 (Book实例,)，所以得到 Book
print(book.bookname)

result = await db.execute(
    select(Book.id, Book.bookname).order_by(Book.id).limit(1)
)
value = result.scalar()  # 第一行是 (1, "Python for Beginners")，所以得到 1
print(value)
```

`scalar()` 无行时返回 `None`，第一列为 SQL `NULL` 时也返回 `None`；多行时只取第一行。`scalar_one()` 则检查是否恰好一行，即使这一行的值为 `NULL`，也满足“一行”，会返回 `None`。

### 2. IteratorResult 与 ChunkedIteratorResult：沿用 Result 方法

这两个类都继承上面介绍的 `Result` 方法。对业务查询来说，不需要再学习另一套 `all()`、`scalar()` 或 `mappings()`。

差别在内部来源：

- `IteratorResult` 使用迭代器提供结果。
- `ChunkedIteratorResult` 进一步支持通过批次提供函数调整内部读取批量，`yield_per()` 会配合这个来源工作。

业务中通常由 SQLAlchemy 创建它们，不需要手动构造。看到 `ChunkedIteratorResult` 后，应继续根据所选字段选择读取方法，而不是寻找一个专门的“转换成 Result”方法。

### 3. CursorResult：还提供游标和语句执行信息

它同样继承全部 `Result` 方法，另外提供与数据库执行有关的信息。常见的是**属性**：

- `returns_rows`：这次执行是否有可读取的结果列；返回零行的 SELECT 通常仍为 `True`。
- `rowcount`：驱动报告的影响行数，常用于 UPDATE／DELETE；普通 SELECT 中可能为 `-1`，不能用作查询总数。
- `inserted_primary_key`、`inserted_primary_key_rows`、`lastrowid`：特定插入执行路径中的主键信息。
- `returned_defaults`、`returned_defaults_rows`：配合相应执行选项取得数据库生成的默认值。
- `is_insert`：是否为插入执行。

```python
result = await db.execute(text("SELECT id FROM book WHERE id = -1"))
print(type(result).__name__)  # CursorResult
print(result.returns_rows)    # True：有结果列
print(result.all())           # []：只是没有匹配行
```

更专门的方法包括 `supports_sane_rowcount()`、`supports_sane_multi_rowcount()`（检查行数报告能力），`last_inserted_params()`、`last_updated_params()`（执行参数），`prefetch_cols()`、`postfetch_cols()`、`lastrow_has_defaults()`（默认值处理信息），以及 `splice_horizontally()`、`splice_vertically()`（组合结果）。

这些不是每次查询都能有效使用的信息，尤其插入属性需要匹配的插入语句。`ChunkedIteratorResult` 没有因为也是 `Result` 就自动拥有这套游标专有信息。

### 4. ScalarResult：已有单个元素，不再提供整行方法

它提供第四节的全部共同方法：`all()/fetchall()`、`first()`、`one()`、`one_or_none()`、迭代、`fetchmany()`、`partitions()`、`unique()`、`yield_per()`、`close()` 和 `closed` 属性。

**它没有** `fetchone()`、`keys()`、`columns()`、`scalar()`、`scalars()`、`mappings()` 等方法。取一项用 `first()`、`one()` 或 `next()`，不用再写 `scalar_result.scalar()`。

```python
stmt = select(Book.id, Book.bookname).order_by(Book.id)
result = await db.execute(stmt)
names_result = result.scalars(index=1)  # index 从 0 开始，1 表示第二列
names = names_result.all()
print(names)  # ["Python for Beginners", "FastAPI Guide", "SQL Basics"]
```

它适合对象列表或单字段列表。已经取出的字符串、整数或 `Book` 实例上，也不能再调用结果集方法。

没有 `fetchone()` 的原因是：一个值可能本来就是 `None`，如果也用 `None` 表示读取结束就会混淆。`next()` 可以区分：

```python
result = await db.execute(
    select(func.max(Book.price)).where(Book.id == -1)
)
values = result.scalars()
print(next(values))             # None：读到聚合结果中的 NULL
print(next(values, "已经读完"))  # 已经读完：没有下一行
```

### 5. MappingResult：保留字段名，取出的行是 RowMapping

它提供第四节的全部共同方法，另外提供 `fetchone()`、`keys()`、`columns(...)`。它没有 `scalar()`、`scalars()`、`scalar_one()` 等方法。

```python
result = await db.execute(
    select(Book.id.label("book_id"), Book.bookname.label("title"))
    .where(Book.id == 1)
)
mappings = result.mappings()
print(list(mappings.keys()))  # ["book_id", "title"]
row = mappings.one()          # RowMapping
print(row["title"])           # Python for Beginners
print(row.get("price", "未查询"))  # 未查询

data = dict(row)              # 转为普通字典
data["title"] = "展示用标题"   # 只修改字典，不更新数据库
```

`MappingResult` 是整批结果的读取对象，不能直接写 `mappings["title"]`。先读到一行后，`RowMapping` 才支持 `row["title"]`、`get()`、`keys()`、`values()`、`items()` 和键是否存在的判断。

`RowMapping` 是只读映射；`label()` 决定结果键名。批量返回字典可以用 `[dict(row) for row in result.mappings().all()]`。

它适合多字段、聚合结果和多表组合结果；但不会自动展开 ORM 实体：

```python
result = await db.execute(select(Book).where(Book.id == 1))
row = result.mappings().one()
print(list(row.keys()))  # ["Book"]
book = row["Book"]
print(book.bookname)     # Python for Beginners
```

`dict(row)` 此时得到的是 `{"Book": Book实例}`。要得到书籍各字段组成的字典，需要明确选择字段或自己从实例属性组织。

## 六、异步结果：形状规则相似，读取方法改为异步

### 1. 三个异步类型

- `await db.stream(stmt)` → `AsyncResult`：异步按行读取。
- `async_result.scalars()` → `AsyncScalarResult`：异步按单个元素读取。
- `async_result.mappings()` → `AsyncMappingResult`：异步按映射读取。
- `await db.stream_scalars(stmt)` 可直接执行并取得 `AsyncScalarResult`。

它们保留相应的读取形状规则，但不是通过继承同步同名类型来获得这种对应关系。

### 2. 哪些方法需要 await

三者的 `all()/fetchall()`、`first()`、`one()`、`one_or_none()`、`fetchmany()` 和 `close()` 需要 `await`；循环使用 `async for`，`partitions(n)` 返回异步批次迭代器。

`AsyncResult` 还提供异步的 `fetchone()`、`scalar()`、`scalar_one()`、`scalar_one_or_none()`；`AsyncMappingResult` 支持异步 `fetchone()`，`AsyncScalarResult` 没有 `fetchone()`。

建立视图或设置读取规则的 `scalars()`、`mappings()`、`unique()`、`yield_per()` 不加 `await`；`keys()`、`columns()`、`tuples()/t` 按相应类型提供，也不等待。它们不会因为结果是异步的，就全都变成协程方法。

```python
stream_result = await db.stream(select(Book).order_by(Book.id))
try:
    print(type(stream_result).__name__)  # AsyncResult
    values = stream_result.scalars()     # 不加 await
    print(type(values).__name__)         # AsyncScalarResult
    async for book in values:
        print(book.id, book.bookname)
finally:
    await stream_result.close()
```

相对地，`await db.scalar(stmt)` 直接得到一个值，`await db.scalars(stmt)` 得到同步读取的 `ScalarResult`。`scalar` 与 `stream` 是不同概念。

流式结果若最终使用 `await values.all()` 收集全部数据，仍需容纳全部结果的内存；ORM 流式加载通常还需合理配置 `yield_per`。更多异步专门方法见 [异步结果 API](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#result-set-api-documentation)。

## 七、所有读取方式都需要记住：结果会被消耗

`scalars()`、`mappings()` 不复制原结果，它们共享读取进度：

```python
result = await db.execute(
    select(Book.id, Book.bookname).order_by(Book.id)
)
values = result.scalars()
mappings = result.mappings()

print(values.fetchmany(1))                # [1]：第一行已被读走
print([row["id"] for row in mappings.all()])  # [2, 3]
print(values.all())                      # []：没有剩余结果
```

`all()` 收集剩余数据，重复调用会得到空列表；`first()`、`scalar()` 或显式 `close()` 会硬关闭结果，之后读取会报错。关闭任意视图也会关闭共享的底层结果，但不会关闭 `db` 会话。

如果需要反复使用数据，保存已读取的列表、字典或对象；如果需要重新执行查询，再调用 `db.execute(stmt)`。

选择方法时，先确定一行里有什么，再决定需要的形状与数量：整行用 `Result`，每行一个元素用 `ScalarResult`，按字段名保留整行用 `MappingResult`；需要几条，再选 `all()`、`first()`、`one()` 等读取方法。
