"""工作台 API 客户端：同步 httpx，可注入 transport 以便单测。

买家对话走 Python Agent（`/api/v1/chat`），审批与审计走 Java（`/api/after-sales`、`/api/audit`）。
网络错误统一转成 `WorkbenchError`，UI 只需要处理一种异常。
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

    def _request(self, base: str, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            with self._client(base) as client:
                return client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise WorkbenchError(f"无法连接服务：{exc}") from exc

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
        resp = self._request(
            self.java_base,
            "POST",
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        return self._json(resp)

    def chat(self, token: str, thread_id: str, message: str) -> dict:
        resp = self._request(
            self.agent_base,
            "POST",
            "/api/v1/chat",
            json={"thread_id": thread_id, "message": message},
            headers=self._auth(token),
        )
        return self._json(resp)

    def thread_messages(self, token: str, thread_id: str) -> list[dict]:
        """固定会话的历史消息（买家自己的，或坐席查看任意）。"""
        resp = self._request(
            self.agent_base,
            "GET",
            f"/api/v1/threads/{thread_id}/messages",
            headers=self._auth(token),
        )
        return self._json(resp)

    def resume(self, token: str, thread_id: str, approved: bool, note: str = "") -> dict:
        resp = self._request(
            self.agent_base,
            "POST",
            f"/api/v1/threads/{thread_id}/resume",
            json={"approved": approved, "note": note},
            headers=self._auth(token),
        )
        return self._json(resp)

    def handoffs(self, token: str) -> list[dict]:
        """坐席转接待办（Python 侧按 pending 标记扫描 interrupt）。"""
        resp = self._request(
            self.agent_base, "GET", "/api/v1/handoffs", headers=self._auth(token)
        )
        return self._json(resp)

    def pending_after_sales(self, token: str, status: str = "PENDING") -> list[dict]:
        resp = self._request(
            self.java_base,
            "GET",
            "/api/after-sales",
            params={"status": status},
            headers=self._auth(token),
        )
        return self._json(resp)

    def my_after_sales(self, token: str) -> list[dict]:
        """买家查自己的售后请求（Java 侧按 user_id 过滤）。"""
        resp = self._request(
            self.java_base, "GET", "/api/after-sales", headers=self._auth(token)
        )
        return self._json(resp)

    def review(self, token: str, request_no: str, approved: bool, note: str) -> dict:
        resp = self._request(
            self.java_base,
            "POST",
            f"/api/after-sales/{request_no}/review",
            json={"approved": approved, "note": note},
            headers=self._auth(token),
        )
        return self._json(resp)

    def audit(self, token: str, limit: int = 20) -> list[dict]:
        resp = self._request(
            self.java_base,
            "GET",
            "/api/audit",
            params={"limit": limit},
            headers=self._auth(token),
        )
        return self._json(resp)
