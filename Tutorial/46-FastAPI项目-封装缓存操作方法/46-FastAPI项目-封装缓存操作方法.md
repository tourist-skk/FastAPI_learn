# FastAPI项目-封装缓存操作方法

上一章把 Redis 服务端装好了，本章在 [config/cache_conf.py](../../toutiao_backend/config/cache_conf.py) 里创建客户端并封装了五个操作函数。

本篇逐个讲解这些函数，并记录实测中发现的**三个问题** —— 其中一个会让 `set_cache()` 完全不工作，另一个会让 Redis 挂掉时接口从 0.2 毫秒变成 3 秒。第五节给出修正后的完整版本。

前置笔记：[45 · 缓存简介及安装 Redis 服务端](../45-FastAPI项目-缓存简介及安装Redis服务端/45-FastAPI项目-缓存简介及安装Redis服务端.md)。

环境：**redis-py 8.1.0 / Redis server 8.10.2**。演示用的 Redis 为临时实例，跑完已关闭。

## 一、这一层要解决什么

完全可以在每个 CRUD 函数里直接调 `redis_client.get()`、`redis_client.set()`。封装一层的意义在于把四件事集中处理：

| 要解决的 | 不封装会怎样 |
| --- | --- |
| **序列化** | Redis 只存字符串，每处都要自己 `json.dumps` / `json.loads` |
| **过期时间** | 容易漏写 TTL，写出永不过期的缓存 |
| **容错** | Redis 挂了要能降级，不能让业务接口跟着 500 |
| **可替换** | 哪天换成别的缓存，只改这一个文件 |

这和 `db_conf.py` 把数据库引擎和 `get_db()` 集中起来是同一个思路：**基础设施的细节收在 config 层，业务层只管调。**

## 二、创建 Redis 客户端

```python
import redis.asyncio as redis

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)
```

### 2.1 导入的是 `redis.asyncio`

项目是异步的，所以用 `redis.asyncio` 而不是顶层的 `redis`。两者 API 几乎一样，区别是前者的方法都要 `await`。

> `redis-py` 从 4.2 起内置异步支持，**不需要再装 `aioredis`** —— 那个包已经并入 redis-py 并停止维护。网上很多旧教程还在教 `aioredis`，看到就可以跳过了。

### 2.2 `db=0` 是什么

Redis 单实例默认有 **16 个逻辑数据库**，编号 0~15，彼此隔离。`db=0` 是默认那个。

它常被误当成"多租户隔离"来用，但实际上这 16 个库共享同一个进程和同一份内存，`FLUSHALL` 会一起清掉，也不能跨库查询。**实践中一般只用 db 0，靠键名前缀来分区**（比如 `news:1`、`user:token:abc`），需要真正隔离时起多个 Redis 实例。

### 2.3 `decode_responses=True` 做了什么

这个参数决定了读出来的是 `str` 还是 `bytes`。实测：

```text
decode_responses=True  -> '中文内容'   类型 str
decode_responses=False -> b'\xe4\xb8\xad\xe6\x96\x87\xe5\x86\x85\xe5\xae\xb9'  类型 bytes
```

Redis 协议层面传的是字节。不开这个参数，每次读出来都要自己 `.decode("utf-8")`，`json.loads()` 虽然能直接吃 bytes，但打日志、做比较时都很别扭。**开着就对了。**

### 2.4 为什么客户端写成模块级全局对象

```python
redis_client = redis.Redis(...)      # 模块顶层，只创建一次
```

`redis.Redis(...)` 内部自带**连接池**。写在模块顶层意味着整个应用共用一个池，连接可以复用。

如果在每个函数里 `redis.Redis(...)` 新建一个，每次调用都要重新建立 TCP 连接 —— 和数据库的 `create_async_engine` 全局只建一次是同一个道理（见 [13-SQLAlchemy学习路线](../00-python基础补充/13-SQLAlchemy学习路线.md) 第二节）。

## 三、五个函数逐个看

### 3.1 为什么读取分成两个函数

```python
async def get_cache(key: str) -> Any:          # 拿原始字符串
    return await redis_client.get(key)

async def get_json_cache(key: str) -> Any:     # 拿回 dict / list
    value = await redis_client.get(key)
    if value is None:
        return None
    return json.loads(value)
```

因为 **Redis 里存的永远是字符串**。存进去的是 dict，取出来的也是一串 JSON 文本，不会自动变回 dict。实测：

```text
get()        -> '{"id": 1, "title": "AI"}'  类型 str
json.loads() -> {'id': 1, 'title': 'AI'}    类型 dict
```

拆成两个函数的好处是**调用方明确知道自己要什么**：存计数器、存 token 用 `get_cache`，存对象和列表用 `get_json_cache`。

注意 `get_json_cache` 里那个 `if value is None: return None` 不能省 —— `json.loads(None)` 会抛 `TypeError`，而缓存未命中返回 `None` 是最常见的情况。

### 3.2 `set_cache`：序列化 + 过期时间

```python
async def set_cache(key: str, value: Any, expire: int = 3600) -> bool:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return await redis_client.setex(key, value, ex=expire)
```

两个设计点是对的：

- **`expire: int = 3600` 给了默认值。** 上一章说过，TTL 应该是默认动作而不是可选项 —— 就算失效逻辑写错了，数据最多也只错一小时。
- **`ensure_ascii=False`。** 不加这个，中文会被转义成 `中文` 存进 Redis，体积翻三倍，用 `redis-cli` 看的时候也全是乱码。

但这个函数有个 bug，见下一节。

### 3.3 `delete_cache` 与 `check_cache`

```python
async def delete_cache(key: str) -> bool:
    return await redis_client.delete(key)

async def check_cache(key: str) -> bool:
    return await redis_client.exists(key)
```

功能没问题。`DEL` 和 `EXISTS` 都是幂等的 —— 删一个不存在的键不会报错，只是返回 0。

## 四、实测发现的三个问题

### 4.1 `set_cache()` 完全不工作

直接调用它，实测：

```text
设置缓存失败: BasicKeyCommands.setex() got an unexpected keyword argument 'ex'
   set_cache 返回: False
   redis 里真的有吗: 0  (0=没有)
```

**这个函数从来没有成功写入过任何数据。** 原因是 `setex` 的参数顺序：

```python
setex(self, name, time, value)      # 真实签名：键、秒数、值
set  (self, name, value, ex=None)   # 真实签名：键、值、过期秒数
```

现在的写法 `setex(key, value, ex=expire)` 犯了两个错：
1. 把 `value` 放在了 `time` 的位置
2. `ex=` 是 `set()` 的参数，`setex()` 不接受 → `TypeError`

两种正确写法都实测通过：

```python
await redis_client.setex(key, expire, value)     # setex(键, 秒数, 值)
await redis_client.set(key, value, ex=expire)    # set(键, 值, ex=秒数)
```

```text
t:a: 值='hello'  TTL=60
t:b: 值='hello'  TTL=60
```

**推荐用 `set(..., ex=...)`** —— `setex` 在 redis-py 里已经标记为废弃：

```text
DeprecationWarning: Call to deprecated setex. (Use 'set' instead.) -- Deprecated since version 2.6.12.
```

`set()` 还更灵活，可以带 `nx=True`（不存在才设）、`xx=True`（存在才设）等参数。

> **这个 bug 最值得注意的不是它本身，而是它被 `try/except` 吞掉了。** 一个 `TypeError`（纯粹的代码写错）被当成"设置缓存失败"打印出来，返回 `False`，程序继续跑。如果不是专门去查，只会看到"缓存好像没生效"，很难想到是参数写反了。第六节再谈这个。

### 4.2 Redis 挂掉时，每次调用要等 3 秒

容错逻辑本身是成立的 —— 把 Redis 关掉后，四个函数都没有抛异常：

```text
get_cache        返回 None     耗时 3482.7 ms
get_json_cache   返回 None     耗时 4113.7 ms
delete_cache     返回 False    耗时 4556.8 ms
check_cache      返回 False    耗时 3745.9 ms
```

接口确实不会 500。**但每次调用要等 3.5~4.5 秒。**

对照上一章的数据：这些接口直接查 SQLite 只要 0.2 毫秒。也就是说 Redis 一挂，接口从 0.2 毫秒变成 4 秒 —— **比完全不用缓存糟糕两万倍。** 这种"降级"还不如直接报错。

原因是 redis-py 8.x 的默认重试策略：

```text
重试次数 retries : 10
退避策略 backoff : ExponentialWithJitterBackoff
   _base = 0.01
   _cap = 1
```

**默认重试 10 次，指数退避最长每次 1 秒。** 连接被拒绝这种"一看就没戏"的错误，它也会老老实实重试 10 轮。

改掉之后实测：

```text
默认配置（项目当前写法）                      2890 ms 后失败  ConnectionError
retry=Retry(NoBackoff(), 0)  关闭重试          1 ms 后失败  ConnectionError
+ socket_connect_timeout=0.2                 1 ms 后失败  ConnectionError
```

**从 2890 毫秒降到 1 毫秒。** 缓存是"锦上添花"的东西，它不可用时应该**立刻放弃、走数据库**，而不是拖着整个请求陪它重试。

### 4.3 两个小问题

**返回类型和签名对不上。** `delete_cache` 和 `check_cache` 声明返回 `bool`，实际返回 `int`：

```text
check_cache 存在的键    -> 1  类型 int   （签名声明是 bool）
check_cache 不存在的键   -> 0  类型 int
delete_cache 存在的键   -> 1  类型 int
delete_cache 不存在的键  -> 0  类型 int
```

`DEL` 返回的是"删掉了几个键"，`EXISTS` 返回的是"存在几个键"。因为 `0` 是假、`1` 是真，用在 `if` 里不出错，但类型注解是骗人的。包一层 `bool()` 就好。

**`bool` 和 `None` 存不进去。** 现在的判断是 `isinstance(value, (dict, list))`，其他类型直接丢给 Redis。实测：

```text
str    存入 '文本'    -> 取出 '文本'      类型 str
int    存入 42       -> 取出 '42'       类型 str   ← 类型丢了
float  存入 3.14     -> 取出 '3.14'     类型 str
dict   存入 {'a': 1} -> 取出 '{"a": 1}'  类型 str
bool   存入 True     -> ❌ DataError: Invalid input of type: 'bool'
None   存入 None     -> ❌ DataError: Invalid input of type: 'NoneType'
```

`None` 存不进去是个实际问题 —— 上一章讲的**缓存穿透**，对策正是"把空结果也缓存起来"。现在这个实现做不到。

## 五、修正后的版本

```python
import json
import logging
from typing import Any

import redis.asyncio as redis
from redis.backoff import NoBackoff
from redis.retry import Retry

logger = logging.getLogger("uvicorn.error")

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True,
    socket_connect_timeout=1,          # 连接超时 1 秒
    socket_timeout=1,                  # 读写超时 1 秒
    retry=Retry(NoBackoff(), 1),       # 最多重试 1 次，不退避
)


async def set_cache(key: str, value: Any, expire: int = 3600) -> bool:
    try:
        # 注意 bool 要单独判断：isinstance(True, int) 是 True
        if isinstance(value, bool) or not isinstance(value, (str, int, float, bytes)):
            value = json.dumps(value, ensure_ascii=False)
        return bool(await redis_client.set(key, value, ex=expire))
    except Exception:
        logger.warning("设置缓存失败 key=%s", key, exc_info=True)
        return False


async def get_cache(key: str) -> str | None:
    try:
        return await redis_client.get(key)
    except Exception:
        logger.warning("读取缓存失败 key=%s", key, exc_info=True)
        return None


async def get_json_cache(key: str) -> Any:
    try:
        value = await redis_client.get(key)
        return None if value is None else json.loads(value)
    except Exception:
        logger.warning("读取缓存失败 key=%s", key, exc_info=True)
        return None


async def delete_cache(key: str) -> bool:
    try:
        return bool(await redis_client.delete(key))
    except Exception:
        logger.warning("删除缓存失败 key=%s", key, exc_info=True)
        return False


async def check_cache(key: str) -> bool:
    try:
        return bool(await redis_client.exists(key))
    except Exception:
        logger.warning("检查缓存失败 key=%s", key, exc_info=True)
        return False
```

六种类型实测全部通过：

```text
字符串  set_cache=True  redis 里存的='文本'                        TTL=60
整数   set_cache=True  redis 里存的='42'                         TTL=60
字典   set_cache=True  redis 里存的='{"id": 1, "title": "AI 新闻"}' TTL=60
列表   set_cache=True  redis 里存的='[1, 2, 3]'                   TTL=60
布尔   set_cache=True  redis 里存的='true'                        TTL=60
None  set_cache=True  redis 里存的='null'                        TTL=60
```

dict 往返一致：

```text
读回 {'id': 1, 'title': 'AI 新闻', 'tags': ['科技']}  类型 dict
往返后数据一致? True
```

### 5.1 那个 bool 判断为什么要单独写

```python
if isinstance(value, bool) or not isinstance(value, (str, int, float, bytes)):
```

我第一版写的是 `if not isinstance(value, (str, int, float, bytes))`，结果 `bool` 还是报 `DataError`。原因是 Python 的一个经典陷阱：

```text
isinstance(True, int) = True
True == 1 = True
```

**`bool` 是 `int` 的子类**，所以 `True` 能通过 `isinstance(value, int)` 的检查，直接被丢给了 Redis。必须在前面单独拦一道。

这个坑不只出现在这里 —— 任何用 `isinstance(x, int)` 做分支的地方，都要想一下 `True/False` 会不会误入。

## 六、`try/except` 该怎么写

现在五个函数的写法是：

```python
try:
    ...
except Exception as e:
    print(f"获取缓存失败: {e}")
    return None
```

有两个可以改进的地方。

### 6.1 `except Exception` 捕获得太宽

4.1 那个 bug 就是被它掩盖的：一个 `TypeError`（代码写错了）和一个 `ConnectionError`（Redis 挂了）走了同一条路径，都被报成"设置缓存失败"。

理想情况下应该只捕获**预期内的、和缓存可用性有关的**异常：

```python
from redis.exceptions import RedisError

except RedisError:          # 只接 Redis 自己的异常
    logger.warning(...)
    return None
```

这样 `TypeError` 会直接冒出来，在开发阶段一眼就能发现。不过 `json.loads` 的 `JSONDecodeError` 也需要接住（缓存里存了坏数据的情况），所以实际会是：

```python
except (RedisError, json.JSONDecodeError):
    ...
```

上面第五节我保留了 `except Exception` 的写法，是为了改动最小；但配了 `exc_info=True`，堆栈会完整打出来，不至于像 `print(e)` 那样只剩一行。

### 6.2 用 `logging` 而不是 `print`

`print` 的问题：

- 不分级别 —— 没法只看 warning 以上
- 不带时间戳、模块名
- 生产环境通常把日志收集到文件或日志系统，`print` 到 stdout 容易丢
- 没有堆栈

项目在 [utils/exception.py](../../toutiao_backend/utils/exception.py) 里已经用了 `logging.getLogger("uvicorn.error")` 配 `exc_info=exc`（见第 44 节 9.3），缓存这里沿用同一套就好。

## 七、还缺什么

这一层目前够用，但离"能上生产"还差几件事：

| 缺什么 | 为什么需要 |
| --- | --- |
| **键名规范** | 现在键名由调用方随手写。应该约定前缀，如 `news:detail:{id}`、`news:category:list`，便于排查和批量删除 |
| **配置外置** | `REDIS_HOST` 等硬编码在代码里，换环境要改代码。应该走环境变量（和之前 API Key 的处理一样） |
| **应用关闭时释放连接** | 现在没有关闭逻辑。应该在 FastAPI 的 `lifespan` 里 `await redis_client.aclose()` |
| **空值缓存** | 缓存穿透的对策。修正版已经能存 `None`（存成 `'null'`），但还需要约定一个"这是空结果"的标记和更短的 TTL |
| **批量操作** | `MGET` / `pipeline`，一次网络往返取多个键 |

这些不用现在全做，知道有这些坑就行。

## 八、本篇核对了哪些实际行为

演示用 Redis 为临时实例（跑完已 `shutdown`，未注册 `brew services`）：

| 验证内容 | 结果 |
| --- | --- |
| 现有 `set_cache()` 调用 | **TypeError，从未成功写入**，被 try/except 吞掉后返回 False |
| `setex` 真实签名 | `setex(name, time, value)`，且已废弃（建议用 `set`） |
| 两种正确写法 | `setex(key, 60, "v")` 和 `set(key, "v", ex=60)` 均 TTL=60 |
| `decode_responses` | True → `str`；False → `bytes` |
| 各类型存取 | int/float 取回变 `str`；**bool 和 None 抛 `DataError`** |
| `delete_cache` / `check_cache` 返回类型 | `int`（0/1），签名声明的是 `bool` |
| Redis 关闭时四个函数 | 都不抛异常，但耗时 **3482 ~ 4556 ms** |
| redis-py 默认重试参数 | `retries=10`，`ExponentialWithJitterBackoff(base=0.01, cap=1)` |
| 关闭重试后的失败速度 | **1 ms**（从 2890 ms 降下来） |
| `isinstance(True, int)` | `True` —— bool 是 int 的子类 |
| 修正版六种类型 | str / int / dict / list / bool / None 全部写入成功，dict 往返一致 |

相关笔记：[45 · 缓存简介及安装 Redis 服务端](../45-FastAPI项目-缓存简介及安装Redis服务端/45-FastAPI项目-缓存简介及安装Redis服务端.md)、[13-SQLAlchemy学习路线](../00-python基础补充/13-SQLAlchemy学习路线.md)。
