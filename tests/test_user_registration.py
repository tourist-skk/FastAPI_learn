"""注册事务回归测试：使用独立数据库，不修改项目中的用户数据。"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1] / "toutiao_backend"
sys.path.insert(0, str(BACKEND_DIR))

from crud import users
from models.Bases import ModelBase
from models.users import User, UserToken
from routers.users import router


class UserRegistrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="registration-test-")
        database = Path(self.temporary.name) / "test.db"
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{database}")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: ModelBase.metadata.create_all(
                    sync_connection, tables=[User.__table__, UserToken.__table__]
                )
            )

        # 复用真正的 get_db，替换它创建会话时使用的数据库。
        self.session_patch = patch("config.db_conf.AsyncSessionLocal", self.sessions)
        self.session_patch.start()
        app = FastAPI()
        app.include_router(router)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        )
        self.payload = {"username": "transaction_test", "password": "Test-password-123!"}

    async def asyncTearDown(self):
        await self.client.aclose()
        self.session_patch.stop()
        await self.engine.dispose()
        self.temporary.cleanup()

    async def row_counts(self):
        async with self.sessions() as session:
            user_count = await session.scalar(select(func.count()).select_from(User))
            token_count = await session.scalar(select(func.count()).select_from(UserToken))
        return user_count, token_count

    async def test_registration_commits_user_and_token(self):
        response = await self.client.post("/api/user/register", json=self.payload)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], 200)
        self.assertEqual(body["data"]["userInfo"]["username"], self.payload["username"])
        self.assertEqual(await self.row_counts(), (1, 1))
        async with self.sessions() as session:
            user = await session.get(User, body["data"]["userInfo"]["id"])
            token = (await session.execute(select(UserToken))).scalar_one()
            self.assertNotEqual(user.password, self.payload["password"])
            self.assertEqual(token.user_id, user.id)
            self.assertEqual(token.token, body["data"]["token"])

    async def test_duplicate_username_does_not_create_more_rows(self):
        first = await self.client.post("/api/user/register", json=self.payload)
        self.assertEqual(first.status_code, 200)

        response = await self.client.post("/api/user/register", json=self.payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "用户名已存在")
        self.assertEqual(await self.row_counts(), (1, 1))

    async def test_token_failure_rolls_back_both_rows_and_allows_retry(self):
        create_token = users.create_user_token

        async def fail_after_token_insert(db, user_id):
            await create_token(db, user_id)
            raise RuntimeError("模拟令牌写入后的异常")

        with patch.object(users, "create_user_token", new=fail_after_token_insert):
            response = await self.client.post("/api/user/register", json=self.payload)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(await self.row_counts(), (0, 0))
        retry = await self.client.post("/api/user/register", json=self.payload)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(await self.row_counts(), (1, 1))

    async def test_commit_failure_returns_error_and_rolls_back(self):
        with patch.object(AsyncSession, "commit", side_effect=RuntimeError("模拟提交失败")):
            response = await self.client.post("/api/user/register", json=self.payload)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(await self.row_counts(), (0, 0))

    async def test_existing_token_is_updated_without_creating_another(self):
        response = await self.client.post("/api/user/register", json=self.payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        async with self.sessions() as session:
            token = await users.create_user_token(session, data["userInfo"]["id"])
            self.assertNotEqual(token.token, data["token"])
            replacement = token.token
            await session.commit()

        self.assertEqual(await self.row_counts(), (1, 1))
        async with self.sessions() as session:
            stored = (await session.execute(select(UserToken))).scalar_one()
            self.assertEqual(stored.token, replacement)


if __name__ == "__main__":
    unittest.main()
