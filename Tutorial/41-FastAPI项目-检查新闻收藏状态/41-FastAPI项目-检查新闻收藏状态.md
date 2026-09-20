# FastAPI 项目-检查新闻收藏状态

核心思路:
1. 前端发送GET请求到 `/api/favorite/check?newsId=123`，其中 `123` 是新闻ID。
2. 后端根据当前token获取用户ID。
3. 后端查询数据库，检查用户是否收藏了该新闻。
4. 前端根据返回结果更新收藏状态。

重点: 前后端接收和返回的字段保持一致的问题
路由构造data的键 is_favorite 和 isFavorite,在 响应类 FavoriteCheckResponse 中 也需要不一致
