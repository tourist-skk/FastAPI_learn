# 30 · FastAPI 项目：数据库、外键、级联与 ORM 配置

本篇围绕项目中的两份初始化脚本学习：

- [MySQL 版本：mysql-database.sql](../../sql/mysql-database.sql)
- [SQLite 版本：sqlite-database.sql](../../sql/sqlite-database.sql)

先理解 MySQL 建表语句，再理解外键和级联，最后对照 SQLite 的改写方式。本文的 MySQL 说明以 MySQL 8.4 / InnoDB 文档为参考；SQLite 行为使用本项目 Python 环境中的 SQLite 3.50.4 实际验证。MySQL 脚本未在本次笔记整理过程中连接服务器执行。

## 1. 先看清项目的数据关系

### 1.1 `.sql` 文件和数据库是什么关系？

`.sql` 是保存 SQL 语句的文本文件。执行它，才会创建表、索引、约束并插入数据。

MySQL 是数据库服务器，同一个服务器中可以创建多个数据库；本脚本选择的数据库名是 `news_app`。SQLite 通常直接把数据库保存在本地文件中，例如 `sql/news_app.sqlite3`，也可以使用临时的内存数据库。

两份脚本都定义了以下 8 张业务表：

| 表 | 保存什么 | 与其他表的关系 |
| --- | --- | --- |
| `user` | 用户账号、资料 | 被令牌、收藏、历史、聊天记录引用 |
| `user_token` | 登录令牌和过期时间 | 每条令牌属于一个用户 |
| `news_category` | 新闻分类 | 一个分类可以有多篇新闻 |
| `news` | 标题、正文、分类、浏览量 | 每篇新闻属于一个分类 |
| `related_news` | 新闻之间的推荐关联 | 同时引用两篇新闻 |
| `favorite` | 用户收藏了哪篇新闻 | 同时引用用户和新闻 |
| `history` | 用户浏览了哪篇新闻、浏览时间 | 同时引用用户和新闻 |
| `ai_chat` | 用户提问和 AI 回复 | 每条聊天记录属于一个用户 |

```mermaid
erDiagram
    user ||--o{ user_token : user_id
    user ||--o{ favorite : user_id
    user ||--o{ history : user_id
    user ||--o{ ai_chat : user_id
    news_category ||--o{ news : category_id
    news ||--o{ favorite : news_id
    news ||--o{ history : news_id
    news ||--o{ related_news : news_id
    news ||--o{ related_news : related_news_id
```

`||--o{` 表示：一条父表记录可以对应零条或多条子表记录，而每条子表记录在这里必须对应一条父表记录。

### 1.2 从表结构中读出业务约定

- 用户和新闻通过 `favorite` 形成多对多收藏关系。
- `favorite` 对 `(user_id, news_id)` 设置唯一约束，因此同一用户不能重复收藏同一篇新闻。
- `history` 没有对这两个字段设置唯一约束，所以同一用户可以多次浏览同一篇新闻。
- `related_news` 中 `(1, 2)` 表示“新闻 1 关联新闻 2”，不会自动生成反向的 `(2, 1)`。
- 当前 `related_news` 没有限制两列不能相等，所以 `(1, 1)` 也能插入；是否禁止自关联，需要额外约束或业务校验。
- `news.author` 是作者名称字符串，没有外键指向 `user`，因此删用户不会因为这个字段而删除新闻。

## 2. MySQL 建库与建表语法

### 2.1 创建数据库并选择它

脚本开头：

```sql
CREATE DATABASE IF NOT EXISTS news_app
DEFAULT CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE news_app;
```

| 片段 | 含义 |
| --- | --- |
| `CREATE DATABASE` | 创建数据库 |
| `IF NOT EXISTS` | 同名数据库已经存在时不重复创建，不会修改已有库的配置 |
| `DEFAULT CHARACTER SET utf8mb4` | 设置默认字符集，可以表示中文和 Emoji 等 Unicode 字符 |
| `COLLATE utf8mb4_unicode_ci` | 设置字符串比较和排序规则，`ci` 表示不区分大小写 |
| `USE news_app` | 当前连接后续未指定库名的操作使用 `news_app` |
| `;` | 一条 SQL 语句结束 |

字符集决定如何表示字符；排序规则决定字符串如何比较、排序，也会影响唯一性判断。

**当前脚本有一个容易忽略的细节：**数据库指定了 `utf8mb4_unicode_ci`，但每张表又单独写了 `DEFAULT CHARSET=utf8mb4`，没有显式写表级 `COLLATE`。MySQL 对“只指定表字符集”的情况会使用该字符集的默认排序规则，不能直接断言所有表都采用数据库那一行的排序规则。[MySQL 表字符集与排序规则](https://dev.mysql.com/doc/refman/8.4/en/charset-table.html)

建表后可以检查实际结果：

```sql
SHOW CREATE DATABASE news_app;
SHOW CREATE TABLE news_app.`user`;
SHOW FULL COLUMNS FROM news_app.`user`;
```

若要求各环境使用同一规则，应在建表或迁移中明确声明。已有表也不会因为重新执行 `CREATE TABLE IF NOT EXISTS` 而自动改变规则。

### 2.2 一条建表语句由什么组成？

下面从原脚本摘取用户表的一部分，用来观察结构，并非替换完整用户表的脚本：

```sql
CREATE TABLE IF NOT EXISTS `user` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  `username` VARCHAR(50) NOT NULL COMMENT '用户名',
  PRIMARY KEY (`id`),
  UNIQUE INDEX `username_UNIQUE` (`username` ASC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户信息表';
```

可以分成三部分：表名、括号内的字段与约束、括号后的表选项。

- 反引号用于引用 MySQL 的表名、字段名等标识符；单引号用于字符串值。
- `COMMENT` 是保存在数据库结构中的说明，不执行业务逻辑；脚本中的 `-- 注释` 是 SQL 文本注释。
- `ENGINE=InnoDB` 选择 InnoDB 存储引擎，本项目利用它的事务和外键能力。
- `IF NOT EXISTS` 只解决“对象是否存在”，不会检查旧表是否与当前建表语句完全相同。

完整语法见 [MySQL CREATE TABLE](https://dev.mysql.com/doc/refman/8.4/en/create-table.html)。

## 3. 字段类型、默认值和时间字段

### 3.1 逐段读懂主键字段

```sql
`id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户ID'
```

| 片段 | 含义 |
| --- | --- |
| `id` | 列名 |
| `INT` | 整数类型 |
| `UNSIGNED` | 无符号，`INT UNSIGNED` 的范围是 0 到 4294967295 |
| `NOT NULL` | 不允许缺失值 `NULL` |
| `AUTO_INCREMENT` | 插入时可以由数据库分配递增编号 |
| `COMMENT '用户ID'` | 字段说明 |

`AUTO_INCREMENT` 不等于主键，真正的主键由 `PRIMARY KEY (id)` 声明。自动编号也不保证连续，不能用 `MAX(id)` 推算记录总数，统计记录数应使用 `COUNT(*)`。

### 3.2 脚本中常见的字段声明

| 声明 | 在本项目中的含义 |
| --- | --- |
| `VARCHAR(50)` | 可变长度字符串，MySQL 中声明的长度按字符计；用户名使用它 |
| `VARCHAR(255)` | 密码哈希、图片地址等较短字符串 |
| `TEXT` | 新闻正文、聊天消息等长文本 |
| `ENUM('male', 'female', 'unknown')` | 枚举字段，从给定值中选择 |
| `NULL DEFAULT NULL` | 允许缺失，未提供时默认缺失，例如昵称、手机号 |
| `NOT NULL DEFAULT 0` | 不允许缺失，未提供时取 0，例如浏览量 |
| `TIMESTAMP` | 时间字段，例如创建时间、令牌过期时间 |

`NULL`、空字符串 `''` 和数字 `0` 是不同值。查询缺失值应使用 `IS NULL`，而不是 `= NULL`：

```sql
SELECT id, username FROM `user` WHERE phone IS NULL;
```

`gender` 在原脚本中允许 `NULL`。`DEFAULT 'unknown'` 表示省略该字段时使用默认值，并不禁止显式写入 `NULL`。MySQL 对非法枚举值的拒绝或转换也受 SQL 模式影响，严格模式下通常会报错。[MySQL ENUM](https://dev.mysql.com/doc/refman/8.4/en/enum.html)

`password` 字段的注释写着“加密存储”，更准确的说法是存储密码哈希。列名和注释都不会自动完成哈希计算，注册逻辑需要负责处理密码。

### 3.3 两种 `ON UPDATE` 不是同一件事

```sql
`created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
`updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
             ON UPDATE CURRENT_TIMESTAMP
```

- `DEFAULT CURRENT_TIMESTAMP`：插入记录、未显式提供该字段时，使用当前时间。
- `ON UPDATE CURRENT_TIMESTAMP`：其他字段的值发生变化且未按规则显式指定该时间列时，自动维护更新时间。
- 它不会持续计时，也不会每秒修改数据库中的时间。
- 如果其他字段没有实际变化，例如 `SET nickname = nickname`，MySQL 自动更新时间通常保持不变。[MySQL 自动时间字段](https://dev.mysql.com/doc/refman/8.4/en/timestamp-initialization.html)

后面外键中的 `ON UPDATE CASCADE` 处理的是**父表被引用的键值发生变化**。一个处理时间字段，一个处理表之间的引用关系。

MySQL 的 `TIMESTAMP` 会按连接时区进行存取转换；`DATETIME` 不采用相同的自动时区转换机制。跨数据库时需要统一时间约定，不能因为字段都叫 `created_at` 就认为语义完全一致。[MySQL 时间类型](https://dev.mysql.com/doc/refman/8.4/en/datetime.html)

## 4. 主键、唯一约束、索引与外键

### 4.1 四个概念分别解决什么问题？

| 概念 | 主要作用 | 本项目例子 |
| --- | --- | --- |
| 主键 `PRIMARY KEY` | 唯一标识本表中的一行，不允许 `NULL` | `user.id` |
| 唯一约束 / 唯一索引 `UNIQUE` | 禁止重复的非空值或值组合 | 用户名不能重复 |
| 普通索引 `INDEX` | 为查询、关联和排序提供访问路径，本身不禁止重复 | `news.category_id` 索引 |
| 外键 `FOREIGN KEY` | 确保引用的数据存在，并定义关联修改规则 | `user_token.user_id` 引用 `user.id` |

主键与唯一约束通常由索引支持，但普通索引不具有唯一约束或外键约束的全部作用。

`user.phone` 允许 `NULL` 且具有唯一约束。当前 MySQL 和 SQLite 设计都允许多条记录的手机号为 `NULL`；非空手机号才不能重复。

### 4.2 联合唯一索引如何理解？

```sql
UNIQUE INDEX `user_news_unique` (`user_id` ASC, `news_id` ASC)
```

它限制的是两列组成的**整组值**：

| `user_id` | `news_id` | 能否与 `(1, 10)` 同时存在？ |
| --- | --- | --- |
| 1 | 10 | 不可以，同一个用户重复收藏同一篇新闻 |
| 1 | 11 | 可以，同一个用户收藏另一篇新闻 |
| 2 | 10 | 可以，另一个用户收藏同一篇新闻 |

它并不要求 `user_id` 单独唯一，也不要求 `news_id` 单独唯一。

### 4.3 索引名称与排序方向

```sql
INDEX `fk_news_category_idx` (`category_id` ASC),
INDEX `idx_publish_time` (`publish_time` DESC)
```

`fk_news_category_idx` 是索引的名字。以 `fk_` 开头只是命名习惯，**写一个名字带 `fk` 的索引，不等于创建了外键**。

`ASC` 表示升序，`DESC` 表示降序。索引中的顺序不会保证普通 `SELECT` 的结果顺序；想让最新新闻在前，仍需要写：

```sql
SELECT id, title, publish_time
FROM news
ORDER BY publish_time DESC, id DESC
LIMIT 10;
```

联合索引 `(user_id, news_id)` 通常也可支持按 `user_id` 查询；只按 `news_id` 查询时，往往仍需要以 `news_id` 开头的索引。脚本中一些单列索引与联合索引的最左列重叠，是否精简应结合查询和外键要求判断。

## 5. 外键：让数据库检查引用关系

### 5.1 父表和子表

以令牌属于用户为例：

```text
user（父表）                     user_token（子表）
id = 1  ←─────────────────────  user_id = 1
                               token = '某个登录令牌'
```

父表是被引用的一方，子表是保存外键的一方。这是相对当前关系的称呼：`news` 对分类来说是子表，对收藏来说又是父表。

假设用户 1 存在，令牌可以引用用户 1；用户 999 不存在时，外键会阻止插入 `user_id=999` 的令牌。也会阻止把已有令牌的 `user_id` 改成不存在的用户。

字段名写成 `user_id` 不会自动产生约束；必须真正声明 `FOREIGN KEY`，并确保数据库执行外键检查。

### 5.2 逐行解释原脚本

以下是 `user_token` 建表语句中的索引和外键部分：

```sql
INDEX `fk_user_token_user_idx` (`user_id` ASC),
CONSTRAINT `fk_user_token_user`
  FOREIGN KEY (`user_id`)
  REFERENCES `user` (`id`)
  ON DELETE CASCADE
  ON UPDATE CASCADE
```

| 代码 | 含义 |
| --- | --- |
| `INDEX ... (user_id)` | 在子表外键列上建立索引 |
| `CONSTRAINT fk_user_token_user` | 给外键约束命名，便于查看和维护 |
| `FOREIGN KEY (user_id)` | 声明当前表的 `user_id` 是外键列 |
| `REFERENCES user (id)` | 外键值引用 `user` 表的 `id` |
| `ON DELETE CASCADE` | 父记录被删除时，自动删除引用它的子记录 |
| `ON UPDATE CASCADE` | 父记录的被引用键值改变时，同步修改子记录的外键值 |

这里有两个不同名字：`fk_user_token_user_idx` 是索引名，`fk_user_token_user` 是约束名。

在本项目的 InnoDB 设计中，父表引用列都是主键。整数外键与被引用列应匹配类型和符号，例如两边都为 `INT UNSIGNED`；子表外键也需要合适索引，InnoDB 在缺少可用索引时可以自动建立。[MySQL 外键要求](https://dev.mysql.com/doc/refman/8.4/en/create-table-foreign-keys.html)

外键列如果允许 `NULL`，缺失引用可以合法存在。本项目这些外键字段均声明为 `NOT NULL`，因此每条子记录都必须有对应父记录。

### 5.3 外键不会帮你做哪些业务处理？

- 外键不会自动查询用户名或新闻标题，关联查询仍需使用 `JOIN` 或 ORM 查询。
- `user_token.expires_at` 到期时，不会因为外键自动删令牌；鉴权逻辑仍需检查过期时间。
- 外键不负责“用户是否有权操作这条数据”，接口仍需校验身份和数据归属。
- 把用户标记为停用或软删除，只是修改状态字段，不会触发 `ON DELETE CASCADE`。

## 6. 级联：父记录变化后，子记录怎么办？

### 6.1 `ON DELETE` 和 `ON UPDATE` 的动作

| 动作 | 用在 `ON DELETE` 时 | 用在 `ON UPDATE` 时 |
| --- | --- | --- |
| `CASCADE` | 删除引用该父记录的子记录 | 同步更新子表外键值 |
| `RESTRICT` | 存在子记录时，拒绝删除父记录 | 存在引用时，拒绝修改被引用键值 |
| `NO ACTION` | 不自动改子记录，按约束检查规则拒绝不合法操作 | 同理 |
| `SET NULL` | 将相应子表外键设置为 `NULL` | 将相应子表外键设置为 `NULL` |
| `SET DEFAULT` | 使用子表外键列的默认值 | 使用子表外键列的默认值 |

本项目使用 `CASCADE` 和 `RESTRICT`。使用 `SET NULL` 要求外键列允许空值；当前脚本的外键列都是 `NOT NULL`，不能直接套用。

MySQL **InnoDB** 中，`NO ACTION` 与 `RESTRICT` 都是立即拒绝违反约束的操作；不支持用 `SET DEFAULT` 实现外键动作。SQLite 支持 `SET DEFAULT`，但默认值仍必须满足外键约束；其 `NO ACTION` 与 `RESTRICT` 在延迟约束的检查时机上也有区别。本项目没有声明延迟外键，入门时先掌握即时检查。[MySQL 参照动作](https://dev.mysql.com/doc/refman/8.4/en/create-table-foreign-keys.html)、[SQLite 外键动作](https://www.sqlite.org/foreignkeys.html#fk_actions)

### 6.2 `CASCADE` 的方向是父记录到子记录

假设用户 1 有两条登录令牌：

```text
删除 user.id = 1
    → 删除 user_token.user_id = 1 的两条令牌

删除其中一条 user_token 记录
    → 用户 1 仍然存在
    → 另一条令牌仍然存在
```

同样，删除一条收藏记录不会删除新闻或用户。级联处理的是符合引用条件的行，不是清空整张子表。

`ON UPDATE CASCADE` 的示意：

```text
父表 user.id：1 → 100
    → 子表 user_token.user_id：1 → 100
```

修改用户名不会触发这条键值级联，因为外键引用的是 `user.id`。实际业务一般保持主键稳定，这个动作主要用来理解约束行为。

### 6.3 本项目全部外键的行为

| 子表外键 | 引用父表字段 | 删除父记录 | 修改父表被引用的键值 |
| --- | --- | --- | --- |
| `user_token.user_id` | `user.id` | 删除该用户令牌 | 同步 `user_id` |
| `news.category_id` | `news_category.id` | **有新闻引用时拒绝删除分类** | 同步 `category_id` |
| `related_news.news_id` | `news.id` | 删除相应关联记录 | 同步 `news_id` |
| `related_news.related_news_id` | `news.id` | 删除相应关联记录 | 同步 `related_news_id` |
| `favorite.user_id` | `user.id` | 删除该用户收藏 | 同步 `user_id` |
| `favorite.news_id` | `news.id` | 删除这篇新闻的收藏记录 | 同步 `news_id` |
| `history.user_id` | `user.id` | 删除该用户浏览历史 | 同步 `user_id` |
| `history.news_id` | `news.id` | 删除这篇新闻的浏览历史 | 同步 `news_id` |
| `ai_chat.user_id` | `user.id` | 删除该用户聊天记录 | 同步 `user_id` |

因此，本项目有 **8 张业务表、9 条外键约束**。

`related_news` 两列虽然都指向 `news.id`，却是两条独立外键：删除新闻 1 时，`(1, 2)` 和 `(2, 1)` 的关联记录都会被删除，但新闻 2 本身仍然保留。

分类使用 `RESTRICT`，是为了避免误删分类时把其下新闻一起删掉。要删除有新闻的分类，可以先将新闻迁移至其他分类，再删除旧分类；具体流程由业务决定。

## 7. 对照 SQLite：哪些语法可以保留，哪些需要改写？

### 7.1 两份脚本的映射

| MySQL 写法 | 当前 SQLite 版本 | 需要理解的差异 |
| --- | --- | --- |
| `CREATE DATABASE`、`USE` | 连接指定 `.sqlite3` 文件 | 库的选择由文件路径完成 |
| `INT UNSIGNED ... AUTO_INCREMENT` | `INTEGER PRIMARY KEY AUTOINCREMENT` | 自增和整数范围语义不同 |
| `VARCHAR(n)` | 仍写 `VARCHAR(n)` | 普通 SQLite 表不自动执行长度上限 |
| `ENUM(...)` | `TEXT` + `CHECK (... IN (...))` | 用检查约束限制字符串取值 |
| `views INT UNSIGNED` | `INTEGER CHECK (views >= 0)` | 当前改写只显式约束浏览量非负 |
| `TIMESTAMP` | `DATETIME` | SQLite 没有专门的日期时间存储类型 |
| `DEFAULT CURRENT_TIMESTAMP` | 保留 | SQLite 生成 UTC 时间文本 |
| `ON UPDATE CURRENT_TIMESTAMP` | `AFTER UPDATE` 触发器 | 需要检查触发条件和递归行为 |
| 列级、表级 `COMMENT` | `--` 文本注释 | 不会作为 MySQL 式注释元数据保存 |
| 表内普通 `INDEX` | 独立 `CREATE INDEX` | SQLite 使用独立建索引语句 |
| 单列 `UNIQUE INDEX` | 列上的 `UNIQUE` | 数据库建立相应唯一索引 |
| 联合 `UNIQUE INDEX` | 独立 `CREATE UNIQUE INDEX` | 仍约束多列组合 |
| `FOREIGN KEY ... REFERENCES ...` | 基本保留 | SQLite 必须确认外键检查已开启 |
| `ON DELETE/UPDATE CASCADE`、`RESTRICT` | 保留 | 外键开启后执行相应动作 |
| `ENGINE`、表级 `CHARSET/COLLATE` | 移除 | 不能原样搬用 MySQL 的表选项 |

SQLite 的普通表采用类型亲和性规则，声明某种类型不意味着像 MySQL 一样严格限制每个存入值。当前脚本也没有使用 `STRICT` 表。[SQLite 数据类型](https://www.sqlite.org/datatype3.html)

### 7.2 外键必须按连接开启

脚本开头有：

```sql
PRAGMA foreign_keys = ON;
```

`PRAGMA` 是 SQLite 的设置和诊断语句。这里启用的是**当前连接**的外键检查，不是往数据库文件里保存一个全局开关。

- 新开一个 CLI、Python 或 ORM 连接，需要再次确保外键开启。
- 常见默认配置下外键检查关闭，但默认值也可能受 SQLite 编译配置影响，应显式设置并查询确认。
- 应在事务开始前启用；在已经进行的事务中改变该设置不会生效。
- 重新开启不会自动修复已有孤儿记录，可以通过 `foreign_key_check` 检查。[SQLite 外键启用方式](https://www.sqlite.org/foreignkeys.html#fk_enable)

```sql
PRAGMA foreign_keys;                 -- 返回 1 表示当前连接已开启
PRAGMA foreign_key_list('user_token'); -- 查看这张表声明的外键
PRAGMA foreign_key_check;            -- 返回违规记录；没有结果表示未发现违规
```

这些命令分别回答“开没开”“定义了什么”“当前数据是否违规”。单看建表 SQL 存在 `FOREIGN KEY`，不能证明连接真的执行了检查。

### 7.3 `INTEGER PRIMARY KEY AUTOINCREMENT`

普通 SQLite 表中，单列 `INTEGER PRIMARY KEY` 可以成为内部 `rowid` 的别名，省略该列时已经能够自动分配整数编号。这里的类型名需要是 `INTEGER`，不能随意替换为 `INT` 来期待同样行为。

额外的 `AUTOINCREMENT` 会记录分配历史，使自动分配的编号不复用过去已提交使用过的编号，也会增加维护开销。它仍不保证编号连续，并不等价于 MySQL 自增实现。[SQLite AUTOINCREMENT](https://www.sqlite.org/autoinc.html)

当前 SQLite 版本没有对所有 ID 字段补上 MySQL `UNSIGNED` 的范围检查，显式插入负的主键值仍可能成功。`views >= 0` 也只限制下界，没有完整模拟 `INT UNSIGNED` 的上界。

### 7.4 `ENUM` 与 `CHECK`

原脚本：

```sql
`gender` ENUM('male', 'female', 'unknown') NULL DEFAULT 'unknown'
```

SQLite 改写：

```sql
"gender" TEXT DEFAULT 'unknown'
    CHECK ("gender" IN ('male', 'female', 'unknown'))
```

`CHECK` 后面是逻辑条件，SQLite 在插入或更新时检查它。这里可以拒绝 `'invalid'`，但仍允许 `NULL`：SQLite 中检查表达式得到 `NULL` 不算失败，且当前字段没有 `NOT NULL`。

若业务要求必须有值，应结合 `NOT NULL`；但这会改变原脚本允许缺失性别的约定，不能当作纯语法翻译悄悄加入。

类似地，`VARCHAR(50)` 在当前 SQLite 表里不自动拒绝 51 个字符的用户名。需要数据库限制时可以另加 `CHECK(length(username) <= 50)`，并在 `schemes` 中同步参数验证。

### 7.5 字符比较与编码不完全相同

当前 SQLite 表没有指定文本排序规则，通常使用默认 `BINARY` 比较。实际验证中，已有 `admin` 后仍能插入 `Admin`；在使用不区分大小写排序规则的 MySQL 用户名列上，两者可能违反唯一约束。

SQLite 的内置 `NOCASE` 也不是 MySQL Unicode 排序规则的完整替代品，不能只改一个名称就认为用户名比较语义一致。[SQLite 比较与排序规则](https://www.sqlite.org/datatype3.html#collation)

SQLite 脚本头注释中的“SQLite 固定 UTF-8”需要更准确地理解：本次创建的库默认使用 UTF-8，但 SQLite 也支持 UTF-16LE / UTF-16BE 数据库编码。可通过 `PRAGMA encoding;` 查看；它没有 MySQL 那套表级 `CHARSET` 语法。[SQLite encoding](https://www.sqlite.org/pragma.html#pragma_encoding)

## 8. SQLite 更新时间触发器逐行讲解

原脚本为 `user`、`news_category`、`news` 建立了三个类似触发器。以用户表为例：

```sql
CREATE TRIGGER IF NOT EXISTS "trg_user_updated_at"
AFTER UPDATE ON "user" FOR EACH ROW
WHEN NEW."updated_at" = OLD."updated_at"
BEGIN
  UPDATE "user"
  SET "updated_at" = CURRENT_TIMESTAMP
  WHERE "id" = NEW."id";
END;
```

| 代码 | 含义 |
| --- | --- |
| `CREATE TRIGGER` | 创建由数据库自动执行的触发器 |
| `IF NOT EXISTS` | 同名触发器存在时不重复创建，也不会更新其旧定义 |
| `trg_user_updated_at` | 触发器名称 |
| `AFTER UPDATE ON user` | 用户表的一行被更新后触发 |
| `FOR EACH ROW` | 每个受影响的行分别执行 |
| `OLD.updated_at` | 更新前这一行的时间值 |
| `NEW.updated_at` | 更新后这一行的时间值 |
| `WHEN ...` | 只有条件成立才执行触发器中的语句 |
| `BEGIN ... END` | 触发器语句块，此处不是开启、提交事务 |
| `WHERE id = NEW.id` | 精确定位刚被更新的那一行，使用更新后的 ID |

通常修改昵称而没有修改时间时，`NEW.updated_at` 和 `OLD.updated_at` 相等，触发器就补写当前时间。[SQLite 触发器](https://www.sqlite.org/lang_createtrigger.html)

### 8.1 `WHEN` 比较的是值，不是 SQL 有没有提到字段

脚本注释说会跳过“应用显式写了 `updated_at`”的情况，实际条件更精确：**只有新旧时间值不同，才会跳过。**

如果应用写的是 `SET updated_at = updated_at`，或者显式赋回相同的时间，新旧值依然相等，触发器仍会执行。

### 8.2 当前触发器与 MySQL 自动更新时间的差异

1. SQLite 的 `AFTER UPDATE` 可以在无实际值变化的更新中触发，例如 `SET username = username`；当前触发器仍可能刷新时间。
2. `CURRENT_TIMESTAMP` 默认精确到秒；同一秒内多次更新，看到相同时间不一定说明触发器失效。
3. 触发器内部又执行一次同表 `UPDATE`。本次环境的 `PRAGMA recursive_triggers` 为 0；如果开启递归触发器，而内层写入的时间仍与旧值相同，当前 `WHEN` 不能阻止反复触发，可能报 `too many levels of trigger recursion`。这一情况已在内存数据库中复现。

可以用 `PRAGMA recursive_triggers;` 查看当前连接的设置。若后续调整触发器，可考虑用不含 `updated_at` 的业务字段列表限制 `AFTER UPDATE OF ...`，或完善触发条件，避免依赖时间值一定变化。要修改已存在的触发器，需通过迁移重建，不能只重新运行带 `IF NOT EXISTS` 的定义。

SQLite 的 `DATETIME` 声明不提供独立的日期时间存储类型，这份脚本的默认时间实际表现为 UTC 文本。与 MySQL `TIMESTAMP` 联调时，应明确保存和展示时区。

## 9. 如何初始化并检查数据库？

### 9.1 MySQL：执行现有脚本

以下为手动操作步骤，先准备已启动的 MySQL 服务和具有建库权限的账号。在项目根目录启动 MySQL 客户端，账号按本机配置替换：

```bash
mysql --default-character-set=utf8mb4 -u root -p
```

在 MySQL 客户端内执行：

```sql
SOURCE sql/mysql-database.sql;
USE news_app;
SHOW TABLES;
SHOW CREATE TABLE user_token;
SHOW INDEX FROM favorite;
SELECT COUNT(*) FROM news;
SELECT @@SESSION.foreign_key_checks;
```

`SOURCE` 是 MySQL 客户端读取脚本的命令；脚本自己已经包含 `CREATE DATABASE` 和 `USE`。原脚本的目标库固定为 `news_app`，不会因为命令行原本选择了另一个库就自动变成测试库。

InnoDB 通常启用外键检查。不应通过关闭 `foreign_key_checks` 来解决正常插入时的引用错误；重新开启也不会自动验证关闭期间写入的全部旧数据。[MySQL 外键检查](https://dev.mysql.com/doc/refman/8.4/en/create-table-foreign-keys.html#foreign-key-checks)

### 9.2 SQLite：创建新的数据库文件

在项目根目录执行，下面选择一个用于新闻项目的新文件名：

```bash
sqlite3 -bail sql/news_app.sqlite3 < sql/sqlite-database.sql
```

`<` 表示将 SQL 文件内容送给 SQLite 执行，`-bail` 表示遇到错误停止。目标文件不存在时会创建，已有文件则会继续操作其中的数据。

再次打开时，是新的连接，需要重新确认外键设置：

```bash
sqlite3 sql/news_app.sqlite3
```

进入 SQLite CLI 后：

```text
.headers on
.mode column
.tables
.schema user_token
```

点号命令是 SQLite CLI 功能，不是可以交给 ORM 执行的 SQL。下面才是 SQL / PRAGMA 语句：

```sql
PRAGMA foreign_keys = ON;
PRAGMA foreign_keys;
PRAGMA foreign_key_list('user_token');
PRAGMA foreign_key_check;
PRAGMA integrity_check;

SELECT COUNT(*) FROM news_category;
SELECT COUNT(*) FROM news;
SELECT COUNT(*) FROM "user";
```

当前 SQLite 脚本在全新内存数据库上的验证结果：8 个分类、403 篇新闻、1 个测试用户，其他 5 张业务表为空；`foreign_key_check` 没有返回违规行，`integrity_check` 返回 `ok`。

### 9.3 `IF NOT EXISTS` 不代表整份脚本可以反复执行

两份脚本的建表语句带有 `IF NOT EXISTS`，但初始化数据使用普通 `INSERT`。

- 再次插入分类名、用户名可能触发唯一约束错误。
- 如果执行工具遇错后继续，新闻等没有对应唯一业务约束的数据可能重复插入。
- 新闻种子数据直接使用分类 ID 1～8，依赖全新初始化时的分类编号。
- SQLite 脚本没有用一个显式事务包住全部初始化；`-bail` 只负责遇错停止，不代表已执行的语句会全部回滚。
- MySQL 的建库、建表等 DDL 具有隐式提交规则，不能认为加一个事务就能回滚整个建库过程。[MySQL 隐式提交](https://dev.mysql.com/doc/refman/8.4/en/implicit-commit.html)

学习时使用全新数据库；项目长期维护则需要将结构迁移与种子数据初始化分别管理。

## 10. 动手验证外键与级联

以下练习在**独立的 SQLite 内存数据库**进行。从项目根目录执行：

```bash
sqlite3 :memory:
```

在这个 CLI 会话中先执行一次：

```text
.read sql/sqlite-database.sql
.headers on
.mode column
```

再确认：

```sql
PRAGMA foreign_keys = ON;
PRAGMA foreign_keys;
```

内存库只在当前连接中存在。下面各实验依次执行，预期报错的语句单独运行；每个成功进入事务的实验最后执行 `ROLLBACK`，恢复初始数据。

### 10.1 外键拒绝不存在的用户

```sql
INSERT INTO user_token (user_id, token, expires_at)
VALUES (900999, 'orphan-demo-token', '2030-01-01 00:00:00');
```

预期：`FOREIGN KEY constraint failed`。因为没有用户 900999，不能建立这条引用。

### 10.2 更新用户 ID，再删除用户

```sql
BEGIN;

INSERT INTO "user" (id, username, password)
VALUES (900001, 'lesson_user', 'demo-hash');

INSERT INTO user_token (user_id, token, expires_at)
VALUES (900001, 'lesson-token', '2030-01-01 00:00:00');

UPDATE "user" SET id = 900002 WHERE id = 900001;

-- 预期 user_id 自动变成 900002。
SELECT user_id, token FROM user_token WHERE token = 'lesson-token';

DELETE FROM "user" WHERE id = 900002;

-- 预期为 0，令牌随用户删除。
SELECT COUNT(*) FROM user_token WHERE token = 'lesson-token';

ROLLBACK;
```

这里的密码值只是填满练习字段，不是注册或密码验证实现。`BEGIN` 开启事务，`ROLLBACK` 撤销事务中的修改；如果改为 `COMMIT`，则表示确认这些修改。外键级联也属于当前事务的一部分。

### 10.3 分类的 `RESTRICT`

先执行：

```sql
BEGIN;
DELETE FROM news_category WHERE id = 1;
```

预期：删除失败，因为初始化数据中还有新闻引用分类 1。然后执行：

```sql
SELECT COUNT(*) FROM news_category WHERE id = 1;
ROLLBACK;
```

预期仍有 1 条分类记录。`RESTRICT` 阻止删除，不会替你把新闻的 `category_id` 改为空。

### 10.4 删除新闻只清理相关记录

以下依赖全新初始化数据中的用户 1、新闻 1 和新闻 2：

```sql
BEGIN;

INSERT INTO favorite (user_id, news_id) VALUES (1, 1);
INSERT INTO history (user_id, news_id) VALUES (1, 1);
INSERT INTO related_news (news_id, related_news_id) VALUES (1, 2);
INSERT INTO related_news (news_id, related_news_id) VALUES (2, 1);

DELETE FROM news WHERE id = 1;

-- 以下三个查询都应为 0。
SELECT COUNT(*) FROM favorite WHERE news_id = 1;
SELECT COUNT(*) FROM history WHERE news_id = 1;
SELECT COUNT(*) FROM related_news WHERE news_id = 1 OR related_news_id = 1;

-- 新闻 2 和用户 1 各自仍有 1 条记录。
SELECT COUNT(*) FROM news WHERE id = 2;
SELECT COUNT(*) FROM "user" WHERE id = 1;

ROLLBACK;
```

完成后输入 `.quit` 关闭内存库。这些操作不会修改 `sql/fastapi.db` 或新闻项目的文件数据库。

## 11. 接入 SQLAlchemy 时，要区分数据库规则和 ORM 规则

### 11.1 引擎、连接和会话

| 名称 | 在后端中的职责 |
| --- | --- |
| `AsyncEngine` | 管理数据库方言、驱动与连接池 |
| 数据库连接 | 实际执行 SQL；SQLite 的外键开关属于这一层 |
| `AsyncSession` | 管理一次业务操作中的 ORM 对象与事务 |
| ORM 模型 | 将 Python 类、属性映射到表和字段 |

本项目已声明两个异步驱动，对应的 SQLAlchemy URL 形式如下。MySQL 地址中的账号、密码为占位值：

```text
mysql+aiomysql://USERNAME:PASSWORD@127.0.0.1:3306/news_app?charset=utf8mb4
sqlite+aiosqlite:///sql/news_app.sqlite3
```

SQLite 这里是相对文件路径，按进程工作目录解析。应从项目根目录启动，或在配置中生成确定的绝对路径，避免意外创建同名空库。

### 11.2 每个 SQLite 新连接都启用外键

以下是可放入数据库配置模块的独立示例，适用于本项目当前 Python 3.11 / `aiosqlite` 的默认连接配置：

```python
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("sqlite+aiosqlite:///sql/news_app.sqlite3")


@event.listens_for(engine.sync_engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
    finally:
        cursor.close()
```

- `connect` 事件在连接池新建底层连接时执行，不是每次 HTTP 请求执行。
- 异步引擎通过 `engine.sync_engine` 注册这种同步风格事件，回调内不写 `await`。
- 应在第一次使用引擎连接数据库前注册监听器。
- 修改驱动的事务或 `autocommit` 配置后，仍需保证 PRAGMA 在事务外执行；不能只在某一次启动会话中设置一次，就认为整个连接池都已经开启。[SQLAlchemy SQLite 外键配置](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#foreign-key-support)

### 11.3 `ForeignKey` 与 `relationship(cascade=...)`

在 ORM 类中的外键字段可以这样声明，以下是字段片段，不是完整用户令牌模型：

```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

user_id: Mapped[int] = mapped_column(
    ForeignKey("user.id", ondelete="CASCADE", onupdate="CASCADE"),
    nullable=False,
)
```

| 配置 | 谁来执行 | 解决什么问题 |
| --- | --- | --- |
| 数据库 `FOREIGN KEY ... ON DELETE CASCADE` | 数据库 | 任何正常 SQL 删除父记录时，都按约束清理子记录 |
| SQLAlchemy `ForeignKey(..., ondelete="CASCADE")` | ORM 的表结构声明 | 建表时表达数据库外键规则 |
| `relationship(cascade="all, delete-orphan")` | ORM 会话的对象管理 | 按配置传播对象操作，或删除脱离父对象集合的子对象 |
| `relationship(passive_deletes=True)` | ORM 与数据库配合 | 删除父对象时，通常将未加载子集合的清理交给数据库级联 |

`delete-orphan` 还包括“子对象从父集合移除后删除它”的语义，比数据库的 `ON DELETE CASCADE` 多一层对象管理行为；二者不能直接画等号。ORM 的删除级联主要作用于会话管理的对象删除，直接 SQL 或批量删除不会自动执行同样的对象遍历。[SQLAlchemy 级联说明](https://docs.sqlalchemy.org/en/20/orm/cascades.html)

只写 `relationship()` 不会自动补出数据库外键。反过来，只在 SQL 文件中写好数据库级联，ORM 关系的删除行为也需要正确配置。

### 11.4 时间默认值与建表方式也要保持一致

- `default=`、`onupdate=` 通常是 SQLAlchemy 发出语句时使用的默认值或更新规则，不等于数据库触发器；直接执行 SQL 时不会自动经过这些 Python 配置。
- `server_default=` 描述数据库端默认值，但“默认当前时间”仍不等于“更新时自动修改”。[SQLAlchemy 默认值与更新规则](https://docs.sqlalchemy.org/en/20/core/defaults.html)
- 如果先执行 SQL 脚本建表，模型应映射已有字段、约束与类型，包括 MySQL 的无符号整数要求。
- 如果改为 ORM 建表，脚本里的 SQLite 触发器不会因为存在普通时间字段而自动生成。
- `Base.metadata.create_all()` 主要创建缺失表，不会把已有表自动迁移成最新模型，也不会自动导入本项目的新闻种子数据。[SQLAlchemy 表结构管理](https://docs.sqlalchemy.org/en/20/core/metadata.html#creating-and-dropping-database-tables)

## 12. 排查清单与复习练习

| 现象 | 优先检查 |
| --- | --- |
| MySQL 建外键失败 | 父表是否存在、类型和 `UNSIGNED` 是否匹配、索引和引擎是否满足要求 |
| 插入令牌报外键错误 | 用户是否已插入，当前 `user_id` 是否真实存在 |
| 删除分类报外键错误 | 分类下是否仍有新闻，是否正是预期的 `RESTRICT` |
| SQLite 能插入不存在的 `user_id` | 当前连接的 `PRAGMA foreign_keys` 是否为 1 |
| CLI 中级联正常，后端中不生效 | 后端连接是否也开启了外键检查 |
| SQLite 存入了超长用户名 | `VARCHAR(n)` 不执行长度限制，检查 Pydantic / `CHECK` 约束 |
| 更新时间没变化 | 是否在同一秒内、触发器是否存在、是否显式提供了不同时间 |
| 更新时间触发器递归报错 | 查看 `recursive_triggers` 和触发条件是否能停止同表递归 |
| 修改脚本后已有表没变化 | `IF NOT EXISTS` 不会更新已有对象，需要结构迁移 |
| 重跑初始化脚本报唯一约束错误 | 种子数据已经存在，普通 `INSERT` 不具备重复执行保护 |

可以按下面的问题检查理解：

1. `user_token.id` 和 `user_token.user_id` 各自负责什么？
2. 为什么索引名叫 `fk_user_token_user_idx`，仍然需要单独声明外键？
3. 删除用户、删除令牌、修改用户名、修改用户 ID，分别会影响哪些记录？
4. 为什么分类采用 `RESTRICT`，令牌采用 `CASCADE`？
5. 为什么收藏不能重复，浏览历史却可以重复？
6. 为什么 SQLite 文件在 CLI 中检查正常，换成 ORM 连接后仍要开启外键？
7. `WHEN NEW.updated_at = OLD.updated_at` 能否准确判断“SQL 没有显式写更新时间”？
8. SQLAlchemy 的 `delete-orphan` 与数据库级联删除有什么不同？

掌握这些规则后，再把连接、会话与 ORM 模型放入 `toutiao_backend/config`、`toutiao_backend/model`，就能知道各项配置究竟由 Python 负责，还是由数据库负责。
