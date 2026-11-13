"""工作台 API 客户端：同步 httpx，可注入 transport 以便单测。

买家对话走 Python Agent（`/api/v1/chat`），审批与审计走 Java（`/api/after-sales`、`/api/audit`）。
"""

from __future__ import annotations

from typing import Any

import httpx


class WorkbenchError(RuntimeError):
    """接口失败，message 带可读原因。"""


class WorkbenchApi:
    def __init__(
        self,
        java_base: str = "http://localhost:8080",
        agent_base: str = "http://localhost:8010",
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.java_base = java_base.rstrip("/")
        self.agent_base = agent_base.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    def _client(self, base: str) -> httpx.Client:
        kwargs: dict[str, Any] = {"base_url": base, "timeout": self.timeout, "trust_env": False}
        if self.transport is not None:
            kwargs["transport"] = self.transport
        return httpx.Client(**kwargs)

    @staticmethod
    def _json(resp: httpx.Response) -> Any:
        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except ValueError:
                payload = None
            detail = None
            if isinstance(payload, dict):
                detail = payload.get("message") or payload.get("detail")
            raise WorkbenchError(f"HTTP {resp.status_code}: {detail or resp.text[:200]}")
        try:
            return resp.json()
        except ValueError as exc:
            raise WorkbenchError("响应不是合法 JSON") from exc

    def _auth(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def login(self, username: str, password: str) -> dict:
        with self._client(self.java_base) as client:
            resp = client.post(
                "/api/auth/login", json={"username": username, "password": password}
            )
        return self._json(resp)

    def chat(self, token: str, thread_id: str, message: str) -> dict:
        with self._client(self.agent_base) as client:
            resp = client.post(
                "/api/v1/chat",
                json={"thread_id": thread_id, "message": message},
                headers=self._auth(token),
            )
        return self._json(resp)

    def resume(self, token: str, thread_id: str, approved: bool, note: str = "") -> dict:
        with self._client(self.agent_base) as client:
            resp = client.post(
                f"/api/v1/threads/{thread_id}/resume",
                json={"approved": approved, "note": note},
                headers=self._auth(token),
            )
        return self._json(resp)

    def pending_after_sales(self, token: str, status: str = "PENDING") -> list[dict]:
        with self._client(self.java_base) as client:
            resp = client.get(
                "/api/after-sales",
                params={"status": status},
                headers=self._auth(token),
            )
        return self._json(resp)

    def my_after_sales(self, token: str) -> list[dict]:
        """买家查自己的售后请求（Java 侧按 user_id 过滤）。"""
        with self._client(self.java_base) as client:
            resp = client.get("/api/after-sales", headers=self._auth(token))
        return self._json(resp)

    def handoffs(self, token: str) -> list[dict]:
        """坐席转接待办（Python 侧扫描 interrupt）。"""
        with self._client(self.agent_base) as client:
            resp = client.get("/api/v1/handoffs", headers=self._auth(token))
        return self._json(resp)

    def review(self, token: str, request_no: str, approved: bool, note: str) -> dict:
        with self._client(self.java_base) as client:
            resp = client.post(
                f"/api/after-sales/{request_no}/review",
                json={"approved": approved, "note": note},
                headers=self._auth(token),
            )
        return self._json(resp)

    def audit(self, token: str, limit: int = 20) -> list[dict]:
        with self._client(self.java_base) as client:
            resp = client.get(
                "/api/audit", params={"limit": limit}, headers=self._auth(token)
            )
        return self._json(resp)
