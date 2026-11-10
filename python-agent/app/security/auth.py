"""对话接口的身份校验。

Java 服务签发 JWT（HS256，claims: sub / userId / role / exp），Python 侧用同一个
密钥本地校验，避免为了取用户身份再绕一次 HTTP。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import jwt
from fastapi import Header, HTTPException

from app.config import settings


@dataclass(frozen=True)
class CurrentUser:
    username: str
    user_id: int
    role: str
    # repr=False：避免日志/异常把 JWT 打印出来
    token: str = field(default="", repr=False)

    @property
    def is_agent(self) -> bool:
        # 兼容 Spring 的 ROLE_CS_AGENT 写法；大小写不敏感，但只认这一个角色
        return self.role.upper().removeprefix("ROLE_") == "CS_AGENT"


def require_user(authorization: str | None = Header(default=None)) -> CurrentUser:
    """从 Bearer 令牌解析用户；任何失败一律 401，不区分原因。"""
    if not settings.jwt_secret:
        raise HTTPException(status_code=401, detail="服务端未配置 JWT_SECRET")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少或无效的令牌")

    token = authorization[7:].strip()
    try:
        # 必须带 exp：否则一个永不过期的令牌可以长期访问（SPEC §6.1：2 小时）
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
        return CurrentUser(
            username=str(claims["sub"]),
            user_id=int(claims["userId"]),
            role=str(claims.get("role", "CUSTOMER")),
            token=token,
        )
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="缺少或无效的令牌") from exc
