"""多模型注册与任务路由。

设计目标：
- 一个 ``task`` 概念（reasoning / fast / local / fallback）→ 一个具体模型；
- 全部走 OpenAI 兼容协议，换供应商只改 .env，不改代码；
- 任何一次调用都要能降级，避免单一供应商抖动把 Agent 打挂。
"""

from dataclasses import dataclass
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

from app.config import settings


@dataclass(frozen=True)
class ModelSpec:
    name: str
    base_url: str
    api_key: str
    label: str


# task -> Settings 字段名
TASK_ROUTES: dict[str, str] = {
    "reasoning": "model_reasoning",
    "fast": "model_fast",
    "local": "model_local",
    "fallback": "model_fallback",
}


def resolve(model: str) -> ModelSpec:
    """按模型名前缀推断供应商（约定优于配置）。"""
    if model.startswith(("qwen", "qwq", "qw-")):
        return ModelSpec(model, settings.qwen_base_url, settings.qwen_api_key or "EMPTY", "qwen")
    if model.startswith("deepseek"):
        return ModelSpec(model, settings.deepseek_base_url, settings.deepseek_api_key or "EMPTY", "deepseek")
    return ModelSpec(model, settings.ollama_base_url, "ollama", "ollama")


def get_chat_model(task: str = "reasoning", *, temperature: float = 0.0, **kwargs: Any) -> ChatOpenAI:
    """按任务取模型。未知 task 回落 reasoning，避免配置写错直接崩。"""
    model_name = getattr(settings, TASK_ROUTES.get(task, "model_reasoning"))
    spec = resolve(model_name)
    return ChatOpenAI(
        model=spec.name,
        base_url=spec.base_url,
        api_key=spec.api_key,
        temperature=temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=1,
        **kwargs,
    )


def with_structured_output(task: str, schema: type, **kwargs: Any) -> BaseChatModel:
    return get_chat_model(task, temperature=0, **kwargs).with_structured_output(schema)


async def ainvoke_with_fallback(
    messages: list[BaseMessage],
    *,
    task: str = "reasoning",
    temperature: float = 0.0,
) -> AIMessage:
    """主模型失败 → 降级到 fallback 模型；两次都失败才抛错。"""
    try:
        return await get_chat_model(task, temperature=temperature).ainvoke(messages)
    except Exception:
        return await get_chat_model("fallback", temperature=temperature).ainvoke(messages)
