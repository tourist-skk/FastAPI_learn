# FastAPI 项目-获取收藏列表

本篇记录当前项目“获取登录用户的收藏列表”的实现，重点理解：**联表查询、排序表达式、分页、多列结果处理、响应字段别名**。

相关代码：[收藏路由](../../toutiao_backend/routers/favorite.py)、[收藏 CRUD](../../toutiao_backend/crud/favorite.py)、[新闻响应模型](../../toutiao_backend/schemes/news.py)、[收藏响应模型](../../toutiao_backend/schemes/favorite.py)、[前端收藏 store](../../xwzx-news/src/store/modules/favorite.js)、[收藏页面](../../xwzx-news/src/views/Favorite.vue)。

## 一、先梳理完整流程

1. 用户进入收藏页面，前端发送 `GET /api/favorite/list?page=1&pageSize=10`，在 `Authorization` 请求头中携带 token。
2. 后端验证 token，取得当前用户；解析页码和每页数量。
3. 联表查询 `news` 和 `favorite`，只取当前用户收藏的新闻，按收藏时间倒序排列，再取指定页的数据。
4. 将多列查询结果转为可以按字段名读取的记录，另查收藏总数，计算是否还有更多数据。
5. 路由用 Pydantic 响应模型包装数据，输出前端需要的 `list`、`hasMore`、`favoriteTime` 等字段。
6. 前端把 `data.list` 保存到收藏 store，页面渲染列表；点击收藏项时，根据新闻 ID 跳转到详情页。

```mermaid
flowchart TD
    A[进入我的收藏页面] --> B[GET /api/favorite/list<br/>page、pageSize、Authorization]
    B --> C[验证 token，取得 user.id]
    C --> D[news 联表 favorite<br/>筛选当前用户]
    D --> E[按收藏时间倒序<br/>offset + limit 分页]
    E --> F[result.mappings().all]
    F --> G[查询 total，计算 has_more]
    G --> H[响应模型校验并转换字段名]
    H --> I[data.list 写入前端 store]
    I --> J[渲染列表，点击跳转新闻详情]
```

完整接口路径是路由前缀 `/api/favorite` 加上 `@router.get("/list")`，即 **`/api/favorite/list`**。

## 二、路由接收哪些参数？

路由参数如下：

```python
@router.get("/list")
async def get_favorite_list(
    page: int = Query(1, ge=1, alias="page", description="页码"),
    page_size: int = Query(10, ge=1, le=100, alias="pageSize", description="每页数量"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await favorite.get_favorite_list(user.id, page, page_size, db)
    total = await favorite.get_favorite_count(user.id, db)
    has_more = (page - 1) * page_size + len(result) < total
    return success_response(
        message="收藏列表成功",
        data=FavoriteListResponse(total=total, has_more=has_more, list=result),
    )
```

| 参数或配置 | 含义 |
| --- | --- |
| `page` | 页码，默认第 1 页 |
| `page_size` | 每页数量，默认 10 条 |
| `ge=1` | greater than or equal，要求值大于等于 1 |
| `le=100` | less than or equal，要求值小于等于 100 |
| `alias="pageSize"` | URL 使用 `pageSize`，Python 函数内使用 `page_size` |
| `Depends(get_db)` | 由依赖提供数据库会话 |
| `Depends(get_current_user)` | 验证 token，并把当前用户对象交给 `user` |

当前用户 ID 来自 `user.id`，不需要前端提交 `user_id`。例如 Tina 登录后，请求的就是 Tina 的收藏列表。

`Query` 的默认值允许前端省略分页参数；如果传入 `page=0` 或 `pageSize=101`，则不满足约束，FastAPI 返回 422。认证过程沿用 [第 41 篇：检查新闻收藏状态](../41-FastAPI项目-检查新闻收藏状态/41-FastAPI项目-检查新闻收藏状态.md)。

## 三、为什么需要联表查询？

`favorite` 表保存的是收藏关系，主要字段为 `id`、`user_id`、`news_id`、`created_at`。页面还要展示标题、图片、作者等新闻内容，因此需要关联 `news` 表。

当前 CRUD 中构造查询的部分如下：

```python
stmt = (
    select(
        News.id,
        News.title,
        News.description,
        News.image,
        News.author,
        News.publish_time,
        News.category_id,
        News.views,
        Favorite.created_at,
    )
    .select_from(News)
    .join(
        Favorite,
        and_(
            Favorite.news_id == News.id,
            Favorite.user_id == user_id,
        ),
    )
    .order_by(Favorite.created_at.desc())
)
```

逐步理解：

- `select(...)`：指定返回的 **9 个字段**，其中 8 个来自新闻表，1 个来自收藏表。
- `.select_from(News)`：明确从新闻表开始查询。
- `.join(Favorite, ...)`：关联收藏表；这里默认是内连接，只保留满足关联条件的记录。
- `Favorite.news_id == News.id`：把收藏关系与对应新闻匹配起来。
- `Favorite.user_id == user_id`：只保留当前用户的收藏。
- `and_(条件1, 条件2)`：生成 SQL 的 `AND`，要求两个条件同时成立。
- `.order_by(...)`：指定查询结果的顺序。

用 SQL 表示，核心结构是：

```sql
SELECT
    news.id, news.title, news.description, news.image,
    news.author, news.publish_time, news.category_id,
    news.views, favorite.created_at
FROM news
JOIN favorite
    ON favorite.news_id = news.id
    AND favorite.user_id = :user_id
ORDER BY favorite.created_at DESC;
```

`:user_id` 表示绑定参数的位置，执行时由 SQLAlchemy 传入当前用户 ID。

注意区分两个 ID 和两个时间：返回的 `id` 是 **`News.id` 新闻 ID**，用于跳转新闻详情；`Favorite.id` 是收藏记录本身的 ID。`publish_time` 是新闻发布时间，`Favorite.created_at` 是该用户收藏这条新闻的时间。

## 四、重点：`order_by()` 的参数到底是什么？

### 4.1 接收的是排序依据，可以传一个或多个

可以把常用调用形式理解为 `order_by(*clauses)`。`*clauses` 表示可以传入多个位置参数，每一个参数描述一项排序依据。常见参数是 SQLAlchemy 的列属性，或者由列生成的 SQL 排序表达式：UnaryExpression 对象（SQLAlchemy 里的一个 SQL 表达式对象）。[SQLAlchemy 官方排序说明](https://docs.sqlalchemy.org/en/20/tutorial/data_select.html#order-by)。

```python
# 直接传列：默认升序
stmt = select(Favorite).order_by(Favorite.created_at)

# 显式指定升序：较早的收藏在前
stmt = select(Favorite).order_by(Favorite.created_at.asc())

# 显式指定降序：较晚的收藏在前
stmt = select(Favorite).order_by(Favorite.created_at.desc())
```

以上三种写法分别对应：

```sql
ORDER BY favorite.created_at
ORDER BY favorite.created_at ASC
ORDER BY favorite.created_at DESC
```

`asc` 来自 ascending，表示升序；`desc` 来自 descending，表示降序。收藏页面通常希望“最近收藏的新闻排在最前面”，所以当前使用 `.desc()`。例如收藏时间为 09:00、12:00、15:00，降序结果就是 15:00、12:00、09:00。

也可以传多个排序依据，优先级从左到右。例如下面是一个**可选扩展示例，当前查询只按收藏时间排序**：

```python
stmt = select(Favorite).order_by(
    Favorite.created_at.desc(),
    Favorite.id.desc(),
)
```

先按收藏时间降序；时间相同时，再按收藏记录 ID 降序。第二个条件可以让相同时间的记录也有确定的先后顺序，便于分页；如果只按时间排序，同一时间的记录之间没有固定顺序保证。

### 4.2 为什么必须写 `desc()`，不能写 `desc`？

#### 先看这三样东西到底是什么

实测打印它们的类型：

```text
Favorite.created_at                type = sqlalchemy.orm.attributes.InstrumentedAttribute
Favorite.created_at.desc           type = builtins.method
Favorite.created_at.desc()         type = sqlalchemy.sql.elements.UnaryExpression
```

`Favorite.created_at.desc` 是一个**普通的 Python 方法对象** —— 注意它的类型是 `builtins.method`，跟 SQLAlchemy 没有任何关系，就是"函数本身"。只有加上括号调用它，才会**生成**一个 SQL 表达式对象 `UnaryExpression`。

到这里为止都是 Python 的常识：`f` 是函数，`f()` 是函数的返回值。但这解释不了一个关键疑问 —— **既然 `Favorite.created_at` 不加括号可以直接传，凭什么 `.desc` 不加括号就不行？** 两个都是"不加括号"，为什么一个行一个不行？

#### 真正的规则：`order_by()` 要的是"SQL 表达式对象"

`order_by()` 从来没有要求"必须带括号"，它要求的是**参数得是一个 SQL 表达式对象**。SQLAlchemy 里所有 SQL 表达式的基类叫 `ColumnElement`。实测判断一下：

```text
                               是 SQL 表达式吗?   可调用吗?
Favorite.created_at                 False          False
Favorite.created_at.desc            False          True
Favorite.created_at.desc()          True           False
```

这里出现了一个看似矛盾的结果：**`Favorite.created_at` 自己居然也不是 SQL 表达式**（`False`），可它明明能直接传给 `order_by()`。

答案在于 SQLAlchemy 的一个协议 —— `__clause_element__()`。实测：

```text
Favorite.created_at 有 __clause_element__ 方法吗?      True
调用它得到: Column('created_at', DateTime(), table=<favorite>, ...)
类型: AnnotatedColumn  ← 这才是真正的 SQL 表达式

Favorite.created_at.desc 有 __clause_element__ 吗?     False
```

`InstrumentedAttribute`（ORM 的列属性）本身是个"代理对象"，它不是 SQL 表达式，但它实现了 `__clause_element__()`，**能够交出一个真正的 SQL 表达式**。SQLAlchemy 接受它，靠的就是这个协议。

所以 `order_by()` 拿到参数后的判断顺序大致是：

```text
1. 它本身就是 SQL 表达式（ColumnElement）吗？
      → 是，直接用                        ← .desc() 走这条
2. 它实现了 __clause_element__() 吗？
      → 是，调用它，取出真正的表达式        ← Favorite.created_at 走这条
3. 两条都不满足
      → 报错                              ← .desc 走这条
```

`Favorite.created_at.desc` 是个 `builtins.method`：它不是 SQL 表达式，也没有 `__clause_element__()`。两条路都走不通，所以被拒绝。

**一句话总结：不是"方法要加括号"，而是"`order_by()` 只认 SQL 表达式"。列属性能直传是因为它有协议可以交出表达式；方法对象什么都交不出来。**

#### 为什么 SQLAlchemy 不干脆替你调用一下？

技术上它当然做得到 —— 看到参数可调用就调一下。但那是**猜**：传进来的可调用对象未必是 `.desc`，也可能是用户随手传错的任何函数，自动调用它可能产生意料之外的副作用，或者得到一个更难懂的错误。

SQLAlchemy 选择的做法是**专门为这个高频笔误加一条针对性的报错**：

```text
sqlalchemy.exc.ArgumentError:
Method <bound method ColumnOperators.desc of <...InstrumentedAttribute object at 0x...>>
may not be passed as a SQL expression
```

这条消息直接点名"方法不能当 SQL 表达式传"，比让它自动调用再出别的问题要好排查。

#### 报错发生在构造阶段，不是执行阶段

这一点对排查很关键。实测两种不同的写错方式：

```text
── 方法对象 .desc
   构造 order_by()  ❌ ArgumentError
      Method <bound method ColumnOperators.desc ...> may not be passed as a SQL expression

── 裸字符串 'created_at DESC'
   构造 order_by()  ✅ 通过
   编译成 SQL      ❌ CompileError
      Can't resolve label reference for ORDER BY / GROUP BY / DISTINCT etc. ...
```

**同样是写错，报错时机可以差好几步：**

| 阶段 | `.desc`（漏括号） | `'created_at DESC'`（裸字符串） |
| --- | --- | --- |
| `order_by()` 构造语句 | ❌ `ArgumentError` | ✅ 通过 |
| 编译成 SQL 字符串 | — | ❌ `CompileError` |
| `await db.execute()` | 根本走不到 | 根本走不到 |

漏写括号时，错误在**构造 `select()` 语句那一行**就抛出来了，`db.execute()` 完全没有执行过，数据库根本没收到任何查询。这正好解释了第九节 9.1 的现象：终端只看到 `ROLLBACK` 而没有 SELECT 日志 —— 因为压根没发出过这条 SELECT。

#### 同一个坑的其他形态

这个规则不只管 `.desc`。实测几个常见的漏括号：

```text
func.count            （漏括号）  ❌ ArgumentError: ORDER BY expression expected, got <...function...>
func.count()                      ✅ 接受
Favorite.created_at.asc （漏括号） ❌ ArgumentError: Method <bound method ColumnOperators.asc ...>
Favorite.id.in_        （漏括号）  ❌ ArgumentError: Method <bound method ColumnOperators.in_ ...>
```

`.asc`、`.in_`、`.like`、`.label`、`func.count` 全是同一回事：**它们都是"用来生成表达式的工具"，不是表达式本身。** 记住这个分类，就不用逐个去背哪个要加括号。

#### `order_by()` 里什么能传、什么不能传

实测汇总：

| 传入 | 结果 |
| --- | --- |
| `Favorite.created_at`（列属性） | ✅ `ORDER BY favorite.created_at` |
| `Favorite.created_at.desc()`（排序表达式） | ✅ `ORDER BY favorite.created_at DESC` |
| `desc(Favorite.created_at)`（函数形式） | ✅ `ORDER BY favorite.created_at DESC` |
| `"created_at DESC"`（裸字符串） | ❌ `CompileError`（编译阶段） |
| `Favorite.created_at.desc`（方法对象） | ❌ `ArgumentError`（构造阶段） |

前三种都能用，因为它们最终都能交出一个 SQL 表达式；后两种交不出来。

### 4.3 `desc()` 会不会立即执行排序？

不会。`.desc()` 只创建 SQL 表达式，`.order_by()` 返回带有排序条件的新查询语句；它们都不会查询数据库。当前代码把返回的语句继续赋给 `stmt` 或用于链式调用。

真正把查询发送给数据库的是：

```python
result = await db.execute(stmt)
```

数据库根据 `ORDER BY` 处理结果顺序。这里需要等待数据库操作，所以使用 `await`；构造 `.desc()` 表达式不需要 `await`。

SQLAlchemy 还提供独立的 `desc()` 函数，下面两种形式可以生成相同的排序条件：

```python
from sqlalchemy import desc

Favorite.created_at.desc()  # 方法形式：操作的列已经绑定
desc(Favorite.created_at)   # 函数形式：需要显式传入列
```

## 五、分页、总数和 `hasMore` 怎样计算？

构造好联表和排序条件后，CRUD 继续添加分页条件：

```python
offset = (page - 1) * page_size
limit = page_size
result = await db.execute(stmt.offset(offset).limit(limit))
return result.mappings().all()
```

`offset` 表示跳过多少条记录，`limit` 表示最多取多少条。例如 `page=2`、`page_size=10`，就跳过排序后的前 10 条，再取最多 10 条。可以理解为先确定整个结果的顺序，再从中取这一页。

`len(result)` 在路由中表示**本页返回条数**。它不能代表总收藏数，因此另有总数查询：

```python
stmt = select(func.count(Favorite.id)).where(Favorite.user_id == user_id)
result = await db.execute(stmt)
return result.scalar_one()
```

`func.count(...)` 生成 SQL 的计数表达式；这个查询没有分页条件。无 `GROUP BY` 的 `COUNT` 查询会返回一行计数结果，所以用 `scalar_one()` 提取该整数；没有收藏时得到 `0`。

这里统计的是当前用户的收藏关系数，列表查询还要求对应新闻存在；在收藏与新闻的关联数据完整时，两者一致。

路由用下面的公式判断还有没有下一页：

```python
has_more = (page - 1) * page_size + len(result) < total
#          已跳过的条数             本页条数     总条数
```

假设总共 23 条收藏，每页 10 条：

| 页码 | 跳过条数 | 本页条数 | 判断过程 | `hasMore` |
| --- | --- | --- | --- | --- |
| 1 | 0 | 10 | `0 + 10 < 23` | `true` |
| 2 | 10 | 10 | `10 + 10 < 23` | `true` |
| 3 | 20 | 3 | `20 + 3 < 23` | `false` |
| 4 | 30 | 0 | `30 + 0 < 23` | `false` |

用户没有收藏时，应正常返回 `list: []`、`total: 0`、`hasMore: false`，不需要先添加一条收藏才能调用此接口。

## 六、为什么使用 `result.mappings().all()`？

本次 `select()` 选出了 9 个独立字段。执行后，`result` 是查询结果对象，需要选择合适的方式读取每行数据。

| 读取方式 | 每行得到什么 | 对本次查询的效果 |
| --- | --- | --- |
| `result.all()` | `Row`，类似元组的行对象 | 保留所有字段，但不是普通字典 |
| `result.scalars().all()` | 默认取每行第一个元素 | 只留下 `News.id`，其他字段被丢弃 |
| `result.mappings().all()` | `RowMapping`，类似字典的映射对象 | 保留所有字段，支持按字段名读取 |

上表是三种读取方式的对比，不应在同一个已读取完的 `result` 上依次调用它们来比较；结果读取会消耗数据。`scalars()` 默认提取第一列的行为也可见 [SQLAlchemy Result 文档](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Result.scalars)。

**注意纠正当前 CRUD 中的一处注释：多列查询调用 `scalars()` 并不会仅仅因为有多列就直接抛出 `InvalidRequestError`。** 本例实际会得到新闻 ID 列表，后续拿这些整数构造需要完整新闻字段的响应模型时才会不匹配。另外，当前选中的是 9 列，不是注释中的 8 列。

使用 `mappings()` 后，可以这样读取一条记录：

```python
rows = result.mappings().all()
if rows:
    row = rows[0]
    print(row["id"])
    print(row["title"])
    print(row["created_at"])
    plain_dict = dict(row)  # 如有需要，可以转换成普通字典
```

本项目直接把 `RowMapping` 列表交给 Pydantic，Pydantic 能按字段名取值，因此不必先逐条转成 `dict`。这一阶段字段仍叫 `publish_time`、`category_id`、`created_at`；转为前端字段名是在后面的响应序列化阶段。

## 七、响应模型怎样与前端保持一致？

### 7.1 复用新闻字段，再加收藏时间

[NewsBase](../../toutiao_backend/schemes/news.py) 是 Pydantic 数据模型，定义新闻响应的公共字段。它不是 SQLAlchemy 的数据库表模型，也不会创建或修改表。

[NewsItemBase](../../toutiao_backend/schemes/favorite.py) 继承 `NewsBase`，因此自动包含新闻 ID、标题、描述、图片、作者、发布时间、分类 ID、浏览量，再增加 `created_at` 表示收藏时间。

先说明当前模型里使用的两个配置：

- `from_attributes=True`：允许校验对象时读取对象属性，例如从 ORM 对象的 `.title` 获取值。本次输入是映射对象，可以直接按键读取，并不依赖这个开关。
- `populate_by_name=True`：字段设置输入别名后，仍允许用 Python 字段名提供输入。例如设置 `alias="list"` 后，既接受 `list=`，也接受 `news_items=`。它不决定输出是否使用别名。

`ConfigDict` 用来集中声明这些模型配置。下面摘录收藏响应模型的关键结构：

```python
class NewsItemBase(NewsBase):
    created_at: datetime = Field(
        ...,
        description="收藏时间",
        serialization_alias="favoriteTime",
    )
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class FavoriteListResponse(BaseModel):
    total: int = Field(..., description="收藏总数")
    has_more: bool = Field(
        ...,
        description="是否有更多数据",
        serialization_alias="hasMore",
    )
    news_items: list[NewsItemBase] = Field(
        ...,
        description="收藏列表",
        alias="list",
    )
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
```

这里 `Field(...)` 中的 `...` 表示必填，`list[NewsItemBase]` 表示列表中的每一项都要按 `NewsItemBase` 校验。`NewsBase` 已定义 `publish_time` 和 `category_id` 的输出别名。

### 7.2 再区分 `alias` 与 `serialization_alias`

“输入”不只指前端请求体。路由执行 `FavoriteListResponse(...)` 时，传给模型构造函数的数据同样是 Pydantic 要校验的输入。

| Python 字段 | 当前配置 | 构造模型时接受的名称 | 按别名序列化后的名称 |
| --- | --- | --- | --- |
| `publish_time` | `serialization_alias="publishTime"` | `publish_time` | `publishTime` |
| `category_id` | `serialization_alias="categoryId"` | `category_id` | `categoryId` |
| `created_at` | `serialization_alias="favoriteTime"` | `created_at` | `favoriteTime` |
| `has_more` | `serialization_alias="hasMore"` | `has_more` | `hasMore` |
| `news_items` | `alias="list"`，并启用 `populate_by_name` | `list` 或 `news_items` | `list` |

`alias` 同时指定输入和输出别名；`serialization_alias` 只指定输出别名。Python 属性名本身不变，例如模型内部仍通过 `.news_items` 读取列表。

所以当前路由这样构造模型是正确的：

```python
data = FavoriteListResponse(total=total, has_more=has_more, list=result)
```

由于启用了 `populate_by_name=True`，写成 `news_items=result` 也可以。如果改成仅使用 `serialization_alias="list"`，就应通过 `news_items=` 构造，因为仅设置输出别名不会让 `list=` 自动成为输入名称。

[success_response()](../../toutiao_backend/utils/response.py) 调用 FastAPI 的 `jsonable_encoder()`，当前默认按别名输出，并将 `datetime` 转成 JSON 可以表示的时间字符串。单独调试 Pydantic 模型时，`data.model_dump()` 默认显示 Python 字段名；要检查接口形式，可以使用 `data.model_dump(mode="json", by_alias=True)`。这里 `mode="json"` 表示转换为适合 JSON 的数据类型，`by_alias=True` 表示使用输出别名。

### 7.3 最终响应示例

下面使用演示数据：

```json
{
  "code": 200,
  "message": "收藏列表成功",
  "data": {
    "total": 1,
    "hasMore": false,
    "list": [
      {
        "id": 1,
        "title": "示例新闻",
        "description": null,
        "image": null,
        "author": null,
        "publishTime": "2026-09-01T09:00:00",
        "categoryId": 1,
        "views": 10,
        "favoriteTime": "2026-09-20T15:00:00"
      }
    ]
  }
}
```

前端读取的是 `response.data.data.list`，因此列表字段必须叫 **`list`**。返回 `newsItems` 或 `news_items`，即使 HTTP 状态码是 200，也不符合当前前端的读取方式。

## 八、前端如何显示结果、跳转详情？

收藏页面挂载时调用 `favoriteStore.getFavoriteListApi()`。该方法默认请求第 1 页、每页 10 条；收到成功响应后执行：

```javascript
this.favorites = response.data.data.list;
```

页面遍历 `favoriteStore.getFavorites`，显示新闻标题、图片、作者、发布时间和收藏时间。点击某一项时执行：

```javascript
router.push(`/news/detail/${id}`);
```

所以查询结果中的 `id` 必须是新闻 ID。当前后端已经支持分页，但收藏页面只在挂载时请求默认页，没有继续读取 `hasMore` 并自动加载后续页；store 当前也是用响应列表替换原数组。

## 九、记录这次遇到的几个问题

### 9.1 看到 `ROLLBACK`，就是查询语句执行失败了吗？

`INFO sqlalchemy.engine.Engine ROLLBACK` 是事务回滚日志，本身不包含异常原因。在一些会话关闭流程中，结束未提交的只读事务也会出现它，不能仅凭这一行认定业务失败。

本次漏写 `.desc()` 括号时，实际过程是：

```text
认证依赖先查询用户，数据库会话已有事务
→ 构造收藏列表查询时，把 .desc 方法传给 order_by
→ SQLAlchemy 抛出 ArgumentError，列表查询尚未发送
→ 异常传到 get_db()，执行 session.rollback()
→ 终端出现 ROLLBACK 日志
```

这里应修复的是 `.order_by(Favorite.created_at.desc())`。给查询补一个 `commit()`，或先向收藏表插入记录，都不能修复表达式写错的问题。

### 9.2 为什么列表接口出错，添加收藏后页面却能显示？

当前前端添加收藏成功后，会调用本地的 `addFavorite(news)`，把正在查看的新闻加入 Pinia store 的 `favorites` 数组，并保存到本地存储。随后进入收藏页面，即使列表 GET 请求失败，store 中已有的数据仍可能被渲染。

因此，“页面出现一条新闻”不能证明“获取收藏列表接口成功”。应在浏览器开发者工具的 **Network** 中找到 `/api/favorite/list` 请求，检查 HTTP 状态码和响应中的 `data.list`。

### 9.3 为什么终端以前只有回滚，没有具体错误？

此前自定义异常处理器接住 SQLAlchemy 异常并返回错误 JSON，却没有主动记录异常。`echo=True` 只负责 SQL 和事务日志；`traceback.format_exc()` 只是把堆栈格式化成字符串，也不会自动打印到终端。

当前 [异常处理模块](../../toutiao_backend/utils/exception.py) 已在 SQLAlchemy 异常处理器中记录日志：

```python
logger = logging.getLogger("uvicorn.error")
logger.error(
    "数据库操作异常：%s %s",
    request.method,
    request.url.path,
    exc_info=exc,
)
```

`exc_info=exc` 表示把该异常的堆栈一起写入日志，因此启动后端的终端能显示出错文件、行号和异常类型。当前 `DEBUG_MODE=True` 还会把 SQLAlchemy 错误详情放进响应，可在 Network → Response 查看 `data.error_detail` 和 `data.traceback`；该开关控制响应详情，不控制上述终端日志。

## 十、复习要点

- 收藏列表查询：当前用户 → 联表取新闻信息 → 收藏时间倒序 → 分页 → 总数 → 响应模型。
- `order_by()` 只认 **SQL 表达式对象**，不是"参数必须带括号"。列属性能直传，是因为它实现了 `__clause_element__()` 协议、能交出真正的表达式；`Favorite.created_at.desc` 只是个 `builtins.method`，什么都交不出来，所以被拒。
- 同类的还有 `.asc`、`.in_`、`.like`、`func.count` —— 它们都是**生成表达式的工具**，不是表达式本身，都要调用。
- 漏写括号在**构造语句那一行**就抛 `ArgumentError`，`db.execute()` 根本没执行，所以终端看不到 SELECT 日志，只剩 `ROLLBACK`。
- `.desc()` 只构造表达式，`await db.execute(...)` 才真正查询数据库。
- 本次查询选择 9 个字段，使用 `mappings().all()` 保留字段名和值；`scalars()` 默认只取第一列。
- 前端要求 `data.list`，收藏时间要求 `favoriteTime`；Python 字段名和响应 JSON 名称通过别名配置衔接。
- 排查失败要看接口响应和异常堆栈，不能只看 `ROLLBACK` 或页面里是否暂时有数据。
