-- 从项目根目录执行：
-- sqlite3 -bail sql/fastapi.db < '23-FastAPI进阶-ORM操作数据-多表查询/update_author_details.sql'
-- 补齐测试资料，并更新旧版 author 表的姓名、国籍约束。
-- SQLite 通过建新表、复制记录、替换旧表来修改此类约束。
-- 作者 ID、姓名、创建时间及已有非空资料保留；整个过程在一个事务中执行。

BEGIN IMMEDIATE;

CREATE TABLE author_replacement (
    author_id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    nationality VARCHAR(100) NOT NULL,
    biography TEXT,
    create_time DATETIME NOT NULL,
    update_time DATETIME NOT NULL,
    CONSTRAINT ck_author_name_not_blank CHECK (length(trim(name)) > 0),
    CONSTRAINT ck_author_nationality_not_blank CHECK (length(trim(nationality)) > 0)
);

-- 填充值仅用于测试；不覆盖已有的非空国籍和简介。
INSERT INTO author_replacement
    (author_id, name, nationality, biography, create_time, update_time)
SELECT
    author_id,
    name,
    CASE WHEN nationality IS NULL OR trim(nationality) = '' THEN
        CASE name
            WHEN 'John Doe' THEN '美国'
            WHEN 'Kate Smith' THEN '英国'
            ELSE '中国'
        END
    ELSE nationality END,
    CASE WHEN biography IS NULL OR trim(biography) = '' THEN
        '测试简介：' || name || '，编程与阅读爱好者，用于多表查询练习。'
    ELSE biography END,
    create_time,
    CASE WHEN nationality IS NULL OR trim(nationality) = ''
           OR biography IS NULL OR trim(biography) = ''
        THEN CURRENT_TIMESTAMP
        ELSE update_time
    END
FROM author;

DROP TABLE author;
ALTER TABLE author_replacement RENAME TO author;
CREATE INDEX ix_author_name ON author (name);

COMMIT;
