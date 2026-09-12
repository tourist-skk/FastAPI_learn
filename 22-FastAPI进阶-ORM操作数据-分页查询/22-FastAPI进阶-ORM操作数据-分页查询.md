# ORM操作数据-分页查询

核心操作: select().offset().limit()

* offset: 跳过 n 条记录
* limit: 取 n 条记录(每页的记录数)

offset 值 = (当前页码 - 1) * 每页数量 limit