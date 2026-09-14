-- 从项目根目录执行：
-- sqlite3 -bail sql/fastapi.db < '23-FastAPI进阶-ORM操作数据-多表查询/init_author.sql'
-- 对应根目录 database_sqlite.py 中的 Author 模型。
-- 已有旧版可空 author 表时，先执行 update_author_details.sql 更新约束。

BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS author (
    author_id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    nationality VARCHAR(100) NOT NULL,
    biography TEXT,
    -- 与模型的 Base 一致，保留创建时间和更新时间。
    create_time DATETIME NOT NULL,
    update_time DATETIME NOT NULL,
    CONSTRAINT ck_author_name_not_blank CHECK (length(trim(name)) > 0),
    CONSTRAINT ck_author_nationality_not_blank CHECK (length(trim(nationality)) > 0)
);

CREATE INDEX IF NOT EXISTS ix_author_name ON author (name);

-- 本次学习数据按姓名去重导入；重复运行时，跳过已有姓名。
-- 国籍和简介是自行编写的测试资料，不表示真实作者信息。
-- 直接执行 SQL 不会触发 ORM 的插入默认值，所以显式填入时间。
INSERT INTO author (name, nationality, biography, create_time, update_time)
SELECT DISTINCT
    b.author,
    CASE b.author
        WHEN 'John Doe' THEN '美国'
        WHEN 'Kate Smith' THEN '英国'
        ELSE '中国'
    END,
    '测试简介：' || b.author || '，编程与阅读爱好者，用于多表查询练习。',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM book AS b
WHERE b.author IS NOT NULL
  AND trim(b.author) <> ''
  AND NOT EXISTS (
      SELECT 1 FROM author AS a WHERE a.name = b.author
  )
ORDER BY b.author;

COMMIT;
