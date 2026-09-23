# 新闻相关的缓存方法
from config.cache_conf import get_json_cache,set_cache
from typing import Any, List, Dict, Optional



# 在查询所有分类时，直接使用如下key就不用再自己定制key。
CATEGORIES_KEY = "news:categories"
NEWS_LIST_KEY = "news:list"
# 实际是存储表的数据。每个字典代表一个分类行数据。
# categories = [
#     {"id": 1, "name": "热点","sort_order":"1"},
#     {"id": 2, "name": "科技","sort_order":"2"},
#     {"id": 3, "name": "体育","sort_order":"3"},
# ]
# 如果需要具体获取新闻列表（特别是分页展示），不能直接设置 "news:list"，否则具体某页的数据取不出来
# 推荐: "news:list:{category_id}:{page}:{page_size}"，其中 page 是分页参数


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

# 写入新闻列表缓存
async def set_cache_news_list(category_id: Optional[int], page: int, page_size: int, news_list: List[Dict[str, Any]], expire: int = 1800) -> bool:
    return await set_cache(f"{NEWS_LIST_KEY}:{category_id if category_id else 'all'}:{page}:{page_size}", news_list, expire)

# 读取新闻列表缓存
async def get_cache_news_list(category_id: Optional[int], page: int, page_size: int) -> Any:
    return await get_json_cache(f"{NEWS_LIST_KEY}:{category_id if category_id else 'all'}:{page}:{page_size}")
