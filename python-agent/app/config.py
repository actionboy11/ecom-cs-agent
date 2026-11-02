"""应用配置：多模型（DeepSeek / 千问 / Ollama）与业务系统地址。"""

from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
