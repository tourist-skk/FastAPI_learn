-- 在项目根目录执行：
-- sqlite3 -bail sql/fastapi.db < '23-FastAPI进阶-ORM操作数据-多表查询/insert_unmatched_records.sql'
-- 准备两本没有作者档案的书，以及两位没有书籍的作者。
-- 在 init_author.sql 之后执行；再次补导所有书籍的作者会改变不匹配状态。

BEGIN IMMEDIATE;

WITH sample_books (bookname, author, price, publisher) AS (
    VALUES
        ('数据库连接练习', '未建档作者甲', 45.0, '连接测试出版社'),
        ('Python多表查询实战', '未建档作者乙', 65.0, '连接测试出版社')
)
INSERT INTO book (bookname, author, price, publisher, create_time, update_time)
SELECT b.bookname, b.author, b.price, b.publisher, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM sample_books AS b
WHERE NOT EXISTS (
    SELECT 1 FROM book WHERE bookname = b.bookname AND author = b.author
);

WITH sample_authors (name, nationality, biography) AS (
    VALUES
        ('无书作者甲', '中国', '测试简介：尚未录入书籍，用于观察作者左连接书籍时的空值和零计数。'),
        ('无书作者乙', '英国', '测试简介：尚未录入书籍，用于对比内连接和左连接的结果。')
)
INSERT INTO author (name, nationality, biography, create_time, update_time)
SELECT a.name, a.nationality, a.biography, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM sample_authors AS a
WHERE NOT EXISTS (
    SELECT 1 FROM author WHERE name = a.name
);

COMMIT;
