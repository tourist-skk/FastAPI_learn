# 15-Pydantic与FastAPI的别名参数

项目里"Python 用蛇形、前端用驼峰"这件事，散落在好几个地方：请求模型用 `alias`、响应模型用 `serialization_alias`、查询参数用 `Query(alias=...)`、请求头用 `Header(alias=...)`。[第 41 节](../41-FastAPI项目-检查新闻收藏状态/41-FastAPI项目-检查新闻收藏状态.md) 因为选错参数还报过一次错。

本篇把这些参数系统地归拢：**先分清"三个阶段"，再看真值表，最后给决策规则。**

读完应当能回答：`alias` / `validation_alias` / `serialization_alias` 该选哪个？`model_dump()` 和 `jsonable_encoder()` 的默认行为为什么不一样？字段一多有没有不用逐个写的办法？

本篇所有结论均实际运行验证，输出原样贴出。环境：**pydantic 2.13.5 / fastapi 0.141.1**。

## 一、先分清"三个阶段"

所有别名参数，本质都是在给**同一个字段在不同阶段的名字**做映射：

```text
外部输入 JSON  →→  Python 属性名  →→  外部输出 JSON
  isFavorite       is_favorite         isFavorite
      ↑                 ↑                   ↑
 validation_alias   字段名本身       serialization_alias
            └──────  alias 同时管这两头  ──────┘
```

一个关键前提：**`alias` 不会重命名 Python 属性**。无论怎么配置，代码里读的永远是 `m.is_favorite`。别名只在"进"和"出"两个边界上起作用，内部一律用字段名。

想不清楚该用哪个参数时，先问自己：**出问题的是"进"还是"出"？**

## 二、核心真值表

以 `is_favorite` 字段、别名 `isFavorite` 为例，实测五种配置：

| 字段配置 | `Model(is_favorite=…)` | `Model(isFavorite=…)` | `model_dump()` | `model_dump(by_alias=True)` |
| --- | --- | --- | --- | --- |
| 无别名 | ✅ | ❌ | `is_favorite` | `is_favorite` |
| `alias="isFavorite"` | ❌ | ✅ | `is_favorite` | `isFavorite` |
| `validation_alias="isFavorite"` | ❌ | ✅ | `is_favorite` | **`is_favorite`** |
| `serialization_alias="isFavorite"` | ✅ | ❌ | `is_favorite` | `isFavorite` |
| `alias` + `populate_by_name=True` | ✅ | ✅ | `is_favorite` | `isFavorite` |

两个容易被忽略的点：

- **`validation_alias` 完全不影响输出。** 即使显式传 `by_alias=True`，出来的仍然是 `is_favorite` —— 它只管"进"。
- **`model_dump()` 默认是 `by_alias=False`。** 不传参数时输出的是字段名，不是别名。（这一点和 `jsonable_encoder()` 相反，见第六节。）

### 三者同时写时谁生效

```python
class A(BaseModel):
    is_favorite: bool = Field(alias="favIn", serialization_alias="favOut")
```

```text
输入只认 favIn；model_dump(by_alias=True) = {'favOut': True}
```

规则很简单：**`validation_alias` 和 `serialization_alias` 各自覆盖 `alias` 的对应半边。** 上例中 `alias` 的输出职责被 `serialization_alias` 接管，只剩下输入职责。

## 三、决策规则：什么情况用哪个

| 你的情况 | 用什么 |
| --- | --- |
| **只做输出**（响应模型），内部用蛇形构造，给前端驼峰 | **`serialization_alias`** |
| **只做输入**（请求模型），前端发驼峰，内部用蛇形 | **`alias`** 或 `validation_alias` |
| 同一个模型**既收又发**，两头都用驼峰 | **`alias`** |
| 既收又发，但**进出名字不一样** | `validation_alias` + `serialization_alias` 分开写 |
| 输入要**兼容多个名字** | `validation_alias=AliasChoices(...)` |
| 输入要从**嵌套结构**里取 | `validation_alias=AliasPath(...)` |
| **整个模型所有字段**都要驼峰 | `model_config` 配 `alias_generator=to_camel` |
| 已有 `alias`，但还想用字段名构造 | 加 `populate_by_name=True` |

**一句话口诀：这个模型是用来"收"的还是用来"发"的？** 收 → `alias`；发 → `serialization_alias`；两者都是 → `alias` + `populate_by_name`。

### 对照项目里的三个模型

| 模型 | 用途 | 当前写法 | 是否合适 |
| --- | --- | --- | --- |
| `FavoriteCheckResponse` | 纯响应，路由内部用 `is_favorite=` 构造 | `serialization_alias` | ✅ 唯一正确选择 |
| `UserUpdatePasswordRequest` | 纯请求，前端发驼峰 | `alias` | ✅ |
| `UserAuthResponse` | 既是响应模型，又要能用字段名构造 | `alias` + `populate_by_name=True` | ✅ |

第 41 节最初用 `alias="isFavorite"` 报错，正是因为它是**纯响应模型**，却被 `alias` 连带改掉了输入名 —— 路由里 `FavoriteCheckResponse(is_favorite=...)` 就对不上了。按上表，纯响应模型应该用 `serialization_alias`。

## 四、三个进阶别名工具

### 4.1 AliasChoices：多个输入名都接受

```python
from pydantic import AliasChoices

class B(BaseModel):
    news_id: int = Field(validation_alias=AliasChoices("newsId", "news_id", "id"))
```

```text
{'newsId': 1}   -> 1
{'news_id': 2}  -> 2
{'id': 3}       -> 3
```

适合做**接口兼容**：前端改字段名的过渡期，新旧两个名字同时接受，等前端全部切换完再删掉旧的。

### 4.2 AliasPath：从嵌套结构里直接取值

```python
from pydantic import AliasPath

class C(BaseModel):
    username: str = Field(validation_alias=AliasPath("user", "profile", "name"))
```

```text
输入 {'user': {'profile': {'name': '小明'}}}  ->  username = '小明'
```

对方给的 JSON 嵌套很深、但你只要其中一两个值时，用它可以省掉一串中间模型。

### 4.3 alias_generator：整个模型自动驼峰

字段一多，逐个写 `Field(alias=...)` 又啰嗦又容易漏。可以让 Pydantic 自动生成：

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class D(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    is_favorite: bool
    news_id: int
    publish_time: str
```

```text
model_dump(by_alias=True) = {'isFavorite': True, 'newsId': 1, 'publishTime': '2024-01-01'}
也能用驼峰构造: D(isFavorite=False, newsId=2, publishTime='x')
```

**如果项目打算全站统一驼峰输出，这是最值得改的一处** —— 做进一个公共 Base 模型，所有 scheme 继承它，就不用再逐个字段写别名了。

## 五、四个开关的区别

| 配置项 | 作用 | 备注 |
| --- | --- | --- |
| `populate_by_name=True` | 有 `alias` 时，**也**允许用字段名输入 | 老名字，仍可用 |
| `validate_by_name=True` | 同上 | 2.11+ 的新名字 |
| `validate_by_alias=True` | 允许用别名输入（默认就是 `True`） | 2.11+ 新增 |
| `serialize_by_alias=True` | 让 `model_dump()` **默认**按别名输出 | 2.11+ 新增 |

`validate_by_alias` 是可以关掉的，关掉后别名反而不认了：

```python
model_config = ConfigDict(validate_by_name=True, validate_by_alias=False)
```

```text
{'is_favorite': True}  ✅
{'isFavorite': True}   ❌ ValidationError  ← 别名反而不认了
```

`serialize_by_alias=True` 能省掉每次写 `by_alias=True`：

```text
alias + serialize_by_alias=True:
  model_dump() = {'isFavorite': True}   ← 不用传 by_alias 了
```

## 六、FastAPI 层的默认值和 Pydantic 不一样

这是最容易混淆的地方：**同一个模型，走不同路径出来的键名不同。**

| 路径 | `by_alias` 默认 | 输出 |
| --- | --- | --- |
| `model_dump()` | **False** | `is_favorite` |
| `jsonable_encoder(obj)` | **True** | `isFavorite` |
| `response_model=R` | **True** | `isFavorite` |
| `response_model=R, response_model_by_alias=False` | — | `is_favorite` |

实测：

```text
jsonable_encoder 签名默认: by_alias=True

jsonable_encoder(r)                             = {'isFavorite': True}
jsonable_encoder(r, by_alias=False)             = {'is_favorite': True}
r.model_dump()                                  = {'is_favorite': True}

response_model=R（默认 response_model_by_alias=True）        -> {'isFavorite': True}
response_model_by_alias=False                               -> {'is_favorite': True}
不声明 response_model，手动 jsonable_encoder（本项目做法）      -> {'isFavorite': True}
```

**记住这条：Pydantic 自己默认不用别名，FastAPI 默认用别名。**

项目里 [success_response()](../../toutiao_backend/utils/response.py) 调用 `jsonable_encoder()` 之所以能输出驼峰，靠的是 FastAPI 的默认值，不是 Pydantic 的。如果哪天改成直接调 `model_dump()`，键名会变回蛇形 —— 这是个无声的行为改变，前端会拿不到字段。

## 七、Query / Header 的 alias 是另一套机制

FastAPI 参数上的 `alias` 和 Pydantic 模型字段的 `alias` 长得一样，但机制不同。

### 7.1 Query：只认别名，没有"两个都行"的开关

```python
@router.get("/check")
async def check(news_id: int = Query(..., alias="newsId")):
    ...
```

```text
GET /q?newsId=1   -> 200 {'news_id': 1}
GET /q?news_id=1  -> 422        ← 只认 alias
```

Pydantic 模型可以用 `populate_by_name=True` 让两种名字都接受，**查询参数没有对应的开关**。写了 `alias` 就只认别名。

### 7.2 Header：下划线会自动转连字符

```text
显式 alias='X-Trace-Id'       -> 200
不写 alias，参数名 x_trace_id  -> 200   ← 自动匹配 x-trace-id 请求头
```

`Header()` 有个默认开启的 `convert_underscores=True`，会把参数名里的下划线转成连字符再去匹配请求头。所以**请求头参数通常不需要写 `alias`**。

项目 [utils/auth.py](../../toutiao_backend/utils/auth.py) 里的 `Header(..., alias="Authorization")`，其实把参数名写成 `authorization` 就能自动匹配，`alias` 可以省掉。HTTP 请求头名本身也是大小写不敏感的。

## 八、小结

- 别名只作用在"进"和"出"两个边界上，**永远不会改变 Python 属性名**。
- `alias` 管两头，`validation_alias` 只管进，`serialization_alias` 只管出；后两者分别覆盖 `alias` 的对应半边。
- 选参数先问"这个模型是收还是发"：收用 `alias`，发用 `serialization_alias`，两者都是就 `alias` + `populate_by_name`。
- `model_dump()` 默认 `by_alias=False`；`jsonable_encoder()` 和 `response_model` 默认 `by_alias=True`。**两者相反，这是最容易踩的坑。**
- 字段多时用 `alias_generator=to_camel` 一次搞定，别逐个写。
- `Query(alias=...)` 只认别名；`Header()` 靠 `convert_underscores` 自动匹配，一般不用写别名。

相关笔记：[12-Pydantic模型配置与序列化](12-Pydantic模型配置与序列化.md)、[第 41 节：检查新闻收藏状态](../41-FastAPI项目-检查新闻收藏状态/41-FastAPI项目-检查新闻收藏状态.md)、[第 35 节：封装通用成功响应格式](../35-FastAPI项目-封装通用成功响应格式/35-FastAPI项目-封装通用成功响应格式.md)。
