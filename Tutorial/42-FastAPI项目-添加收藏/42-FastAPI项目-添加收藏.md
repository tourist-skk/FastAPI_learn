# FastAPI 项目-添加收藏

核心操作:
1. 前端发送POST请求到 `/api/favorite/add`
2. 后端使用请求体参数接收请求，验证用户身份
3. 调用CRUD层添加收藏记录，返回收藏记录
4. 由于UniqueConstraint的存在，重复添加不会创建新记录
5. 返回成功响应
