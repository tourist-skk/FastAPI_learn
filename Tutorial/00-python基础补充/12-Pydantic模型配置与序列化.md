# 12-Pydantic模型配置与序列化

本文从第 35 节「封装通用成功响应格式」抽出，介绍 Pydantic v2 的模型配置（`Config` / `ConfigDict`）以及 `model_validate` / `model_dump` 的用法。

示例沿用项目中的 `schemes/users.py`。核心模型如下：

```python
from pydantic import BaseModel, Field, ConfigDict

class UserInfoResponse(BaseModel):
    id: int
    username: str
    model_config = ConfigDict(from_attributes=True)

class UserAuthResponse(BaseModel):
    token: str
    user_Info: UserInfoResponse = Field(alias="userInfo", description="用户信息")

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
    )
```

## 一、Pydantic 是干什么的

Pydantic 是一个做数据校验和类型转换的库。定义一个类并声明字段类型后，Pydantic 负责：

1. 校验传入的数据是否符合声明的类型。
2. 把数据转换成声明的类型（如字符串 `"30"` 转成整数 `30`）。
3. 数据不对时抛出错误。

```python
class User(BaseModel):
    name: str
    age: int

User(name="张三", age=30)    # 正常
User(name="张三", age="30")  # "30" 自动转成 int 30
User(name="张三", age="abc") # 报错：无法转成 int
```

项目里的 `UserRequest`、`UserInfoResponse`、`UserAuthResponse` 都是这种模型类。

## 二、什么是模型配置

除了字段类型，Pydantic 还提供了一堆可开关的行为开关，用来改变它处理数据的方式，例如：

- 是否允许字段名和别名混用。
- 是否支持从 ORM 对象读取数据。
- 是否允许传入未声明的字段。
- 校验时是否使用严格模式。

这些开关统称为模型配置。每个模型类都可以单独设置。

## 三、v1 的 Config 类 与 v2 的 model_config

Pydantic 有两个大版本，配置的写法完全不同。

### v1 写法：内部类 Config

```python
class User(BaseModel):
    name: str
    age: int

    class Config:
        orm_mode = True
        allow_population_by_field_name = True
```

规则：在模型类里定义一个叫 `Config` 的内部类，把配置项写成它的类属性，Pydantic 会自动读取。

### v2 写法：类属性 model_config

```python
class User(BaseModel):
    name: str
    age: int

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
```

规则：用一个类属性 `model_config`，值是 `ConfigDict` 字典。

### 对照表

| v1 老写法 | v2 新写法 |
|-----------|-----------|
| `class Config:` 内部类 | `model_config` 类属性 |
| `orm_mode = True` | `from_attributes=True` |
| `allow_population_by_field_name = True` | `populate_by_name=True` |

## 四、ConfigDict 是什么

`ConfigDict` 本质上是一个「限定好 key 和类型的字典」。它的实际定义大致如下（简化版）：

```python
class ConfigDict(TypedDict, total=False):
    populate_by_name: bool
    from_attributes: bool
    validate_assignment: bool
    extra: str
    # ... 还有其他配置项
```

`TypedDict` 表示「这个字典里只能出现哪些 key、每个 key 是什么类型」。因此：

- 写错配置名，IDE 会提示。
- 写错类型（比如给 `populate_by_name` 传字符串），IDE 会提示。

它最终会被 Pydantic 读入并变成一个真正的配置对象来生效。

## 五、两个配置项的含义

### populate_by_name=True

Pydantic 里「字段名」和「别名」是两个概念：

- 字段名：Python 内部访问用的名字，一般建议 snake_case，如 `user_Info`。
- 别名：序列化/接口对外的名字，常是 camelCase，如 `userInfo`。

默认情况下，一旦给字段声明了 `alias`，就只认别名、不认字段名。开启 `populate_by_name=True` 后，两种名字都能用于赋值：

```python
UserAuthResponse(userInfo=...)   # ✅ 别名，默认就支持
UserAuthResponse(user_Info=...)  # ✅ 字段名，需要 populate_by_name=True
```

### from_attributes=True

默认 Pydantic 只从 dict / JSON（即请求体）里取值。开启 `from_attributes=True` 后，可以直接传入 ORM 对象（如 SQLAlchemy 模型实例），Pydantic 会通过读取对象属性（`obj.token`、`obj.user_Info`）来填充：

```python
db_user = await db.get(User, 1)          # ORM 对象
UserAuthResponse.model_validate(db_user) # 靠 from_attributes=True 生效
```

在 v1 里对应 `orm_mode=True`。

## 六、model_dump：输出（序列化）

作用：把 Pydantic 模型对象转成 Python 字典，通常用于返回给前端或做 JSON 序列化。

```python
resp = UserAuthResponse(
    token="abc123",
    user_Info=UserInfoResponse(id=1, username="tom"),
)

resp.model_dump()
# 默认结果（by_alias=False，输出字段名）：
# {
#     "token": "abc123",
#     "user_Info": {"id": 1, "username": "tom"}
# }
```

### 关键参数 by_alias

- `by_alias=False`（**默认**）：输出用字段名 `user_Info`，适合 Python 内部使用。
- `by_alias=True`：输出用别名 `userInfo`，适合给前端。

```python
resp.model_dump()                # {"token": "...", "user_Info": {...}}  ← 默认不用别名
resp.model_dump(by_alias=True)   # {"token": "...", "userInfo": {...}}
resp.model_dump(by_alias=False)  # {"token": "...", "user_Info": {...}}
```

> ⚠️ **容易踩的坑：Pydantic 和 FastAPI 的默认值是相反的。**
> `model_dump()` 默认 `by_alias=False`（输出字段名），而 FastAPI 的 `jsonable_encoder()` 和 `response_model` 默认 `by_alias=True`（输出别名）。
> 项目里 `success_response()` 能输出驼峰键，靠的是 `jsonable_encoder()` 的默认值，不是 Pydantic 的。
> 完整对照见 [15-Pydantic与FastAPI的别名参数](15-Pydantic与FastAPI的别名参数.md) 第六节。

### 其他常用参数

| 参数 | 作用 |
|------|------|
| `by_alias=True` | 输出用别名（默认为 `False`，即输出字段名） |
| `exclude_none=True` | 值为 `None` 的字段不输出 |
| `exclude_unset=True` | 只输出主动设置过的字段 |
| `mode="json"` | 转成纯 JSON 兼容类型（如 `datetime` 转字符串） |

## 七、model_validate：输入（反序列化）

作用：把外部数据（字典或 ORM 对象）校验并转成 Pydantic 模型对象，是通用响应封装里关键的一步。

### 从字典构造

```python
data = {
    "token": "abc123",
    "userInfo": {"id": 1, "username": "tom"},
}

resp = UserAuthResponse.model_validate(data)
```

这里 `userInfo` 用的是别名，所以能对上。若字典里是 `user_Info`（字段名），则需要 `populate_by_name=True`。

### 从 ORM 对象构造

```python
db_user = await db.get(User, 1)          # 假设查出的对象
resp = UserAuthResponse.model_validate(db_user)
```

这一步依赖 `from_attributes=True`，否则只认 dict，传 ORM 对象会报错。

## 八、model_validate_json：直接吃 JSON 字符串

`model_validate` 吃的是已解析好的 dict/对象，`model_validate_json` 则直接吃 JSON 字符串，内部先 `json.loads` 再校验：

```python
json_str = '{"token": "abc123", "userInfo": {"id": 1, "username": "tom"}}'

resp = UserAuthResponse.model_validate_json(json_str)
```

| 方法 | 输入类型 | 内部动作 |
|------|----------|----------|
| `model_validate` | dict / ORM 对象 | 直接校验 |
| `model_validate_json` | JSON 字符串 | 先 `json.loads` 再校验 |

## 九、完整的进出流程

结合项目的通用响应封装（`utils/response.py` 的 `success_response`），一条数据的进出如下：

```python
# ① 输入：ORM 对象 → 响应模型（靠 from_attributes=True）
db_user = await db.get(User, 1)
info = UserInfoResponse.model_validate(db_user)

# ② 组装外层响应模型
resp = UserAuthResponse(token="xxx", user_Info=info)

# ③ 输出：响应模型 → 字典，给前端（靠 alias 输出 userInfo）
payload = resp.model_dump(by_alias=True)
# {"token": "xxx", "userInfo": {...}}

# ④ 再包一层通用成功响应
result = {"code": 0, "message": "success", "data": payload}
```

在 FastAPI 中若直接 `return resp`，FastAPI 会自动调用序列化逻辑转成 JSON，别名也会自动生效。

## 十、小结

1. 模型配置 = Pydantic 的行为开关集合。
2. v1 用 `class Config`，v2 用 `model_config = ConfigDict(...)`。
3. `ConfigDict` 是一个限定好 key 和类型的配置字典。
4. `populate_by_name=True` = 允许用字段名（而非只别名）赋值。
5. `from_attributes=True` = 允许从 ORM 对象读取数据。
6. `model_dump` 负责输出（序列化），**默认用字段名**；要输出别名得传 `by_alias=True`。注意 FastAPI 的 `jsonable_encoder()` 默认相反，是用别名的。
7. `model_validate` 负责输入（反序列化），可吃 dict 或 ORM 对象。
8. 别名参数不止 `alias` 一个，还有 `validation_alias` / `serialization_alias` / `AliasChoices` / `alias_generator`，选用规则见 [15-Pydantic与FastAPI的别名参数](15-Pydantic与FastAPI的别名参数.md)。

### 版本对照

| v1 | v2 |
|----|----|
| `.dict()` | `.model_dump()` |
| `.parse_obj()` | `.model_validate()` |
| `.parse_raw()` | `.model_validate_json()` |

继续学习：[第 35 节：封装通用成功响应格式](../35-FastAPI项目-封装通用成功响应格式/35-FastAPI项目-封装通用成功响应格式.md)。
