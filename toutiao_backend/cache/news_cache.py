# 新闻相关的缓存方法
from config.cache_conf import get_json_cache,set_cache
from typing import Any, List, Dict



CATEGORIES_KEY = "news:categories"
# 实际是存储表的数据。每个字典代表一个分类行数据。
# categories = [
#     {"id": 1, "name": "热点","sort_order":"1"},
#     {"id": 2, "name": "科技","sort_order":"2"},
#     {"id": 3, "name": "体育","sort_order":"3"},
# ]

# 获取新闻分类缓存
async def get_news_categories() -> Any:
    return await get_json_cache(CATEGORIES_KEY)

# 写入新闻分类缓存（数据、过期时间）
# 分类、配置: 7200
# 列表：600
# 详情: 1800
# 验证码: 120 -> 数据越稳定，缓存越持久
async def set_news_categories(categories: List[Dict[str, Any]], expire: int = 7200) -> bool:
    return await set_cache(CATEGORIES_KEY, categories, expire)
