# 14-SQLAlchemy 关系 relationship 与关联加载

本篇承接 [13-SQLAlchemy学习路线](13-SQLAlchemy学习路线.md) 中"下一步最值得补的 relationship"这一节，把 `relationship()` 讲完整，并补上理解它绕不开的两个问题：**为什么异步下访问关联属性会报 `MissingGreenlet`，以及 `await` 到底扮演什么角色。**

读完应当能回答：`ForeignKey` 和 `relationship()` 有什么区别？一对多/多对一怎么声明？`selectinload` 解决什么问题？为什么同步访问 `news.category` 没事、异步却报错？

内容依据当前项目模型整理。演示沿用项目里的 `News` ↔ `Category`、`User` ↔ `UserToken` 两组关系。

## 一、一句话定位

`relationship()` 是 **ORM 层的对象导航机制**，让两个模型对象之间可以"顺着属性直接跳过去"，而不用自己再写一条查询。

最关键的区分：

| | `ForeignKey` | `relationship()` |
| --- | --- | --- |
| 属于哪层 | **Core / 数据库层** | **ORM 层** |
| 定义在哪 | 列上（`mapped_column(..., ForeignKey(...))`） | 模型类属性上 |
| 会不会改变数据库 | **会**，产生外键约束 | **不会**，不新增任何列/约束 |
| 作用 | 数据库里两张表怎么"连" | 内存里两个对象怎么"跳" |

项目里现在只写了 `ForeignKey`，数据库层面的外键约束是有的，但 ORM 对象之间没有打通导航路径，所以只能手动查两次。

## 二、为什么需要它

看 [models/news.py](../../toutiao_backend/models/news.py)，`News` 表有 `category_id` 外键指向 `news_category.id`。现在的写法是：

```python
news = await db.get(News, 1)
category = await db.get(Category, news.category_id)   # 手动再查一次
```

有了 `relationship`，可以直接：

```python
news = await db.get(News, 1)
category = news.category   # 直接拿到分类对象
```

本质是：**外键存的是"对方的 id"，relationship 帮你"顺着 id 把对方对象捞回来"。**

## 三、四种关系类型

| 类型 | 数据库里怎么表达 | 例子 |
| --- | --- | --- |
| 多对一 (many-to-one) | "多"的那张表存外键 | 多条新闻属于一个分类 `News.category_id` |
| 一对多 (one-to-many) | 同上（反过来看） | 一个分类下有多条新闻 |
| 一对一 (one-to-one) | 外键 + 唯一约束 | 用户和用户详情 |
| 多对多 (many-to-many) | 需要中间关联表 | 用户和收藏的新闻 |

一对多和多对一是**同一件事的两面**：从"多"看是多对一，从"一"看是一对多。

## 四、怎么声明（SQLAlchemy 2.0 写法）

以 `News` ↔ `Category` 为例，双向关联：

```python
class Category(Base):
    __tablename__ = "news_category"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # 一对多：一个分类下有多条新闻
    news_list: Mapped[list["News"]] = relationship(back_populates="category")


class News(Base):
    __tablename__ = "news"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey("news_category.id"), nullable=False)

    # 多对一：一条新闻属于一个分类
    category: Mapped["Category"] = relationship(back_populates="news_list")
```

几个要点：

- **`ForeignKey` 只写在"多"的那一侧**（`News.category_id`），`Category` 不需要任何外键字段。
- **`relationship` 是纯内存属性**，两边各自声明，用 `back_populates` 把两边对上号。名字（`news_list` / `category`）自己起，两边的 `back_populates=` 要互相指到对方那个属性名。
- 类型注解 `Mapped["Category"]` 用字符串是**前向引用**，因为类还没定义完；文件顶部一般要加 `from __future__ import annotations`。

`User` ↔ `UserToken` 同理（参考 [models/users.py](../../toutiao_backend/models/users.py)）：

```python
class User(Base):
    __tablename__ = "user"
    ...
    tokens: Mapped[list["UserToken"]] = relationship(back_populates="user")


class UserToken(ModelBase):
    __tablename__ = "user_token"
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), nullable=False)
    ...
    user: Mapped["User"] = relationship(back_populates="tokens")
```

如果只需要单向（比如只从 `News` 跳 `Category`，从不需要反查），也可以只在 `News` 上声明，省略 `back_populates`：

```python
class News(Base):
    category: Mapped["Category"] = relationship()   # 单向即可
```

`relationship()` 能从 `Mapped["Category"]` 注解里自动推断目标表和关系类型。

## 五、用起来是什么效果

```python
# 之前：查两次，手动拼
news = await db.get(News, 1)
category = await db.get(Category, news.category_id)

# 之后：一次查，顺着取
news = await db.get(News, 1)
category = news.category          # 多对一，取到单个对象

# 反方向：一对多
category = await db.get(Category, 1)
all_news = category.news_list     # 取到该分类下所有 News 的列表
```

## 六、懒加载、N+1、预加载

`relationship` 默认是 **懒加载（lazy="select"）**：真正访问 `news.category` 那一刻，它才偷偷发一条 `SELECT`。

这带来著名的 **N+1 问题**：

```python
news_list = (await db.execute(select(News).limit(10))).scalars().all()  # 1 次查询
for n in news_list:
    print(n.category.name)   # 每次循环都再查 1 次 → 总共 11 次查询
```

解决办法是**预加载**，一次性把关联数据查出来：

```python
from sqlalchemy.orm import selectinload

stmt = select(News).options(selectinload(News.category)).limit(10)
# selectinload：先查 10 条 news，再用 IN 一次查完它们的 category → 总共 2 次
```

另一个选项是 `joinedload`（用 JOIN 一次查出）。`selectinload` 在"一对多"场景通常更安全，因为 JOIN 会导致主表行膨胀（一条 news 对应多行 category 时，news 会重复出现）。

## 七、异步下的关键坑：MissingGreenlet

这是本项目最需要小心的一点，也是"同步没事、异步报错"的根源。

### 7.1 结论先说

> 异步引擎里，凡是要碰数据库的操作，都必须显式 `await`；而 `relationship` 的懒加载是"藏在属性读取里的隐式 IO"，没法 `await`，所以异步下必须用 `selectinload` 之类的预加载，提前把关联数据显式查出来。

### 7.2 三个基础概念：IO、同步 IO、异步 IO

**IO** = Input/Output，输入输出。程序除了算算术，很多时候要跟"外部世界"交换数据：读写文件、发网络请求、查数据库。它有一个关键特征——**慢**：相对 CPU，一次查库可能慢几千上万倍。等待期间 CPU 是闲的，怎么利用这段等待时间，就是"同步/异步"要解决的问题。

**同步（阻塞）IO**：发起 IO 后**原地干等**，期间当前线程什么都做不了，直到拿到结果。

- 类比**打电话**：拨通后一直占线听对方说话，期间不能干别的。

**异步（非阻塞）IO**：发起 IO 后**不原地等**，先把控制权交出去，去做别的事；等 IO 完成再回来处理结果。

- 类比**发微信**：发出去后不用盯着等，先去干别的，对方回复（弹通知）再回来看。

| | 同步（阻塞） | 异步（非阻塞） |
| --- | --- | --- |
| 等待期间 | 线程被占住，干不了别的 | 线程被让出来，能处理别的事 |
| 结果怎么拿 | 函数返回时直接拿到 | 通过 `await` / 回调拿到 |

### 7.3 隐式 IO 和显式 IO

从"代码能不能看出来在做 IO"的角度分：

- **显式 IO**：一眼能看出在做 IO。

  ```python
  user = await db.get(User, 1)      # 明显在查库
  r = requests.get("http://...")    # 明显在发请求
  ```

- **隐式 IO**：表面上只是读个属性，背后偷偷做了 IO。

  ```python
  category = news.category   # 看着是读属性，其实懒加载偷偷发了 SELECT
  ```

"隐式"的危险在于：你以为只是取内存里的值，结果是发了一次数据库查询。`news.category` 在异步下报错，正是因为它的 IO 被藏起来了。

### 7.4 await 是什么

先纠正一个常见误解：**`await` 不是"把线程卡住等"，而是"把线程让出去等"。**

在 Python 里，`async def` 定义的函数，调用时**并不会马上执行函数体**，而是返回一个协程对象。只有对它 `await`，函数体才会真正跑起来：

```python
async def f():
    return 42

f()          # 只创建协程对象，函数体没执行，什么也没发生
await f()    # 才真正执行，拿到 42
```

所以 `await` 有两个作用：

1. **触发执行**：让那个异步操作真正开始跑。
2. **让出控制权**：等待期间把线程交还给事件循环，让它去跑别的任务；结果出来后再回到这里继续。

事件循环（event loop）可以理解成一个调度器：一个线程里维护一堆任务，哪个在等 IO 就先放着，去跑下一个能跑的，谁 IO 完成了就回去接着处理谁。这就是异步能"一个线程扛住很多并发请求"的原因。更完整的同步/异步基础见 [03-同步与异步](03-同步与异步.md)。

### 7.5 异步引擎下，等结果一定要用 await 吗？

**要，而且是"必须"，不是可选。** 原因有三层：

**第一，不 `await` 协程不会执行。** 直接调用 `db.get(User, 1)` 只得到一个协程对象，什么都不发生。

**第二，异步引擎把"所有数据库 IO"都封装成了协程。** 凡是碰数据库的操作，返回的都是协程，都得 `await` 才能跑：

```python
await db.get(...)              # 必须
await session.execute(...)     # 必须
await db.commit()              # 必须
await db.refresh(obj)          # 必须
```

**第三，异步引擎靠 greenlet 桥接，只有 `await` 这个入口会建立桥接。** SQLAlchemy 内部其实是同步代码，异步引擎只是在每个 `await` 处用 greenlet 把同步 IO"接"到事件循环上。不 `await`，桥接就不建立，同步 IO 接不上事件循环——这就是 `MissingGreenlet` 的根源。

### 7.6 为什么同步不报、异步报

关键点：**SQLAlchemy 的 ORM 核心是同步写的，异步支持只是外面套的一层壳（靠 greenlet 桥接）。**

同步 SQLAlchemy 里，访问 `news.category` 会**当场阻塞**、同步发一条 SELECT 再返回。阻塞是允许的，所以没事。

异步下不一样：

```python
news = await db.get(News, 1)   # ✅ 显式 await，greenlet 桥接正常工作
category = news.category        # ❌ 普通属性访问，没有 await
```

访问 `news.category` 是普通的 Python 属性读取，不可能写成 `await news.category`。但懒加载背后又想偷偷发一条 SELECT（因为 ORM 内部是同步查库）。此刻：

- 你不在任何 `await` 的上下文里，
- 也就没有 greenlet 桥接在运行，
- 同步的 IO 接不上事件循环，

于是直接抛 `MissingGreenlet`，报错里的 `greenlet_spawn has not been called` 就是"这次数据库访问发生在桥接之外"。

所以问题的本质不是"执行顺序"或"没查完跳下一步"，而是：**懒加载 = 隐式 IO；异步规则 = 不能有隐式 IO；两者冲突。**

## 八、落地建议

按依赖顺序，最值得先补的是一对多/多对一（项目马上要用的"新闻 → 分类""用户 → token"）：

```text
News       -> Category   （多对一）+ Category -> News（一对多）
User       -> UserToken  （一对多）+ UserToken -> User（多对一）
```

多对多（收藏、浏览历史）需要中间关联表，放到下一阶段。

异步项目里访问关联属性前，**必须**用 `selectinload()` / `joinedload()` 预加载，不能依赖懒加载：

```python
from sqlalchemy.orm import selectinload

stmt = select(News).options(selectinload(News.category)).where(News.id == 1)
news = (await db.execute(stmt)).scalar_one_or_none()
category = news.category   # ✅ 已经预加载，安全
```

## 九、小结

- `ForeignKey` 管"数据库里怎么连"，`relationship` 管"对象之间怎么跳"；前者是约束，后者是导航。
- `relationship` 默认懒加载，会引发 N+1；用 `selectinload` / `joinedload` 预加载解决。
- 异步项目里懒加载是隐式 IO，接不上事件循环，会抛 `MissingGreenlet`；所以必须显式预加载。

相关笔记：[03-同步与异步](03-同步与异步.md)、[13-SQLAlchemy学习路线](13-SQLAlchemy学习路线.md)、[09-SQLAlchemy查询结果与取值](09-SQLAlchemy查询结果与取值.md)。

继续学习：[第 15 节：ORM 简介及安装](../15-FastAPI进阶-ORM简介及安装/15-ORM学习.md)。
