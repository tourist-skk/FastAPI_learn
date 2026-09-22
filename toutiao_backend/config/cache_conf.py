import json
from typing import Any
import redis.asyncio as redis

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

redis_client = redis.Redis(
    host=REDIS_HOST,  # Redis 服务器的主机地址
    port=REDIS_PORT,  # Redis 端口号
    db=REDIS_DB,  # Redis 数据库编号，0~15
    decode_responses=True  # 是否将字节数据解码为字符串
)

# Redis 使用 key-value 存储，其中key - value 都是 str。如果读取列表和字段，那么在设置时需要序列化
# 读取时也需要特殊处理
async def get_cache(key: str) -> Any:
    try:
        return await redis_client.get(key)
    except Exception as e:
        print(f"获取缓存失败: {e}")
        return None
    
# 读取: 列表或者字典
async def get_json_cache(key: str) -> Any:
    try:
        value = await redis_client.get(key)
        if value is None:
            return None
        # Python 的 json.load() 方法用于从文件对象中读取并反序列化 JSON 数据，将其转换为 Python 对象（如字典或列表）
        return json.loads(value)
    except Exception as e:
        print(f"获取缓存失败: {e}")
        return None

# 设置缓存
# SET 和 SETEX 都是设置键值对，但是 SETEX 可以设置过期时间
async def set_cache(key: str, value: Any, expire: int = 3600) -> bool:
    try:
        # ensure_ascii=False 用于将中文字符转换为 Unicode 编码，而不是转义为 ASCII 字符
        # isinstance() 函数的第二个参数可以是多个类型元组，用于判断一个对象是否是多个类型的中的一个
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        return await redis_client.setex(key, expire,value)
    except Exception as e:
        print(f"设置缓存失败: {e}")
        return False

# 删除缓存
async def delete_cache(key: str) -> bool:
    try:
        return await redis_client.delete(key=key)
    except Exception as e:
        print(f"删除缓存失败: {e}")
        return False

# 检查缓存是否存在
async def check_cache(key: str) -> bool:
    try:
        return await redis_client.exists(key)
    except Exception as e:
        print(f"检查缓存是否存在失败: {e}")
        return False