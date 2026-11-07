"""对话接口的身份校验。

Java 服务签发 JWT（HS256，claims: sub / userId / role），Python 侧用同一个
密钥本地校验，避免为了取用户身份再绕一次 HTTP。
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException

from app.config import settings


@dataclass(frozen=True)
class CurrentUser:
    username: str
    user_id: int
    role: str

    @property
    def is_agent(self) -> bool:
        return self.role == "CS_AGENT"


def require_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    """从 Bearer 令牌解析用户；任何失败一律 401，不区分原因。"""
    if not settings.jwt_secret:
        raise HTTPException(status_code=401, detail="服务端未配置 JWT_SECRET")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少或无效的令牌")

    token = authorization[7:].strip()
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return CurrentUser(
            username=str(claims["sub"]),
            user_id=int(claims["userId"]),
            role=str(claims.get("role", "CUSTOMER")),
        )
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="缺少或无效的令牌") from exc
