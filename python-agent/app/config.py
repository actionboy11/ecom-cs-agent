"""应用配置：多模型（DeepSeek / 千问 / Ollama）与业务系统地址。"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "dev"

    # --- 模型提供商 ---
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ollama_base_url: str = "http://localhost:11434/v1"

    # --- 任务路由：不同任务用不同模型 ---
    model_reasoning: str = "deepseek-chat"   # 意图识别 / 应答生成
    model_fast: str = "qwen-turbo"           # 轻量分类
    model_local: str = "qwen2.5:7b"          # 本地：改写、压缩、打标
    model_fallback: str = "deepseek-chat"    # 主模型失败时降级

    # --- 业务系统 ---
    business_api_base: str = "http://localhost:8080"
    business_api_timeout: float = 5.0

    # --- Agent 会话状态（SQLite，与业务数据分离：ADR-0002） ---
    agent_state_db: str = "data/agent_state.db"

    # --- 鉴权：与 Java 服务共用同一密钥，用于校验对话接口的 JWT ---
    jwt_secret: str = ""

    # --- 内部审计令牌：Python 向 Java 上报越权事件时使用 ---
    internal_audit_token: str = ""

    # --- 知识层（Chroma 本地持久化 + 本地 embedding） ---
    chroma_dir: str = "data/chroma"
    embedding_model: str = "bge-m3"

    # --- 会话数据保留期（天）：超期会话与轨迹会被清理 ---
    session_ttl_days: int = 30

    @field_validator("session_ttl_days")
    @classmethod
    def _ttl_must_be_positive(cls, value: int) -> int:
        # 0 会在下次启动清空所有会话；负数会变成无效的 SQL 修饰符
        if value < 1:
            raise ValueError("SESSION_TTL_DAYS 必须 >= 1")
        return value

    # --- 模型调用超时（秒）；测试里可调小以便快速降级 ---
    llm_timeout_seconds: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
