"""用户信息接口回归测试：使用内存数据库验证路由和令牌认证。"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1] / "toutiao_backend"
sys.path.insert(0, str(BACKEND_DIR))

from main import app
from models.Bases import ModelBase
from models.users import User, UserToken


class UserInfoTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.addAsyncCleanup(self.engine.dispose)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: ModelBase.metadata.create_all(
                    sync_connection, tables=[User.__table__, UserToken.__table__]
                )
            )

        session_patch = patch("config.db_conf.AsyncSessionLocal", self.sessions)
        session_patch.start()
        self.addCleanup(session_patch.stop)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        )
        self.addAsyncCleanup(self.client.aclose)
        self.payload = {"username": "profile_test", "password": "Test-password-123!"}
        response = await self.client.post("/api/user/register", json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.auth_data = response.json()["data"]

    async def test_login_token_returns_profile_with_raw_and_bearer_headers(self):
        response = await self.client.post("/api/user/login", json=self.payload)
        self.assertEqual(response.status_code, 200)
        token = response.json()["data"]["token"]

        for authorization in (token, f"Bearer {token}"):
            with self.subTest(bearer=authorization.startswith("Bearer ")):
                response = await self.client.get(
                    "/api/user/info", headers={"Authorization": authorization}
                )
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["code"], 200)
                self.assertEqual(body["data"], self.auth_data["userInfo"])
                self.assertNotIn("password", body["data"])
                self.assertNotIn("token", body["data"])

    async def test_missing_authorization_is_rejected(self):
        response = await self.client.get("/api/user/info")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["header", "Authorization"]
        )

    async def test_unknown_token_is_rejected(self):
        response = await self.client.get(
            "/api/user/info", headers={"Authorization": "unknown-test-token"}
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "token无效")

    async def test_expired_token_is_rejected(self):
        async with self.sessions() as session:
            token = (await session.execute(select(UserToken))).scalar_one()
            token.expires_at = datetime.now() - timedelta(seconds=1)
            await session.commit()

        response = await self.client.get(
            "/api/user/info", headers={"Authorization": self.auth_data["token"]}
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "token无效")


if __name__ == "__main__":
    unittest.main()
