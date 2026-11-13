"""LLM judge 第二轨：判定「回复是否解决了用户问题」（SPEC §10 双轨）。

与第一轨（子串判事实）分开统计：
- 第一轨：`must_contain` 子串匹配，便宜、确定性；
- 第二轨：LLM 判是否解决，能发现「要点齐全但答非所问」。

没有模型 Key 时抛 `JudgeUnavailable`，调用方应标记「跳过」而不是伪造结果。
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from app.config import settings
from app.llm.registry import get_chat_model


class JudgeUnavailable(RuntimeError):
    """没有可用模型或输出无法解析。"""


@dataclass(frozen=True)
class JudgeResult:
    resolved: bool
    reason: str


PROMPT = """你是电商售后客服的质检员。请判断客服回复是否真正解决了用户的问题。

用户问题：{question}
客服回复：{reply}
必须包含的事实要点：{reference}

只输出 JSON，不要其它文字：
{{"resolved": true, "reason": "一句话理由"}}

判定标准：
- 事实要点齐全、且没有误导用户，才算解决；
- 转人工、要求用户补充信息、答非所问、只说「稍等」都算未解决。"""


def build_prompt(question: str, reply: str, reference: Iterable[str]) -> str:
    points = "；".join(str(p) for p in reference) or "（无）"
    return PROMPT.format(question=question, reply=reply, reference=points)


def parse_judgement(raw: str) -> JudgeResult:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
        return JudgeResult(bool(payload["resolved"]), str(payload.get("reason", ""))[:200])
    except (ValueError, KeyError, TypeError):
        match = re.search(r'"resolved"\s*:\s*(true|false)', text, re.IGNORECASE)
        if match:
            return JudgeResult(match.group(1).lower() == "true", "从非严格 JSON 中解析")
        raise JudgeUnavailable(f"无法解析 judge 输出: {raw[:120]}") from None


async def judge_reply(
    question: str,
    reply: str,
    reference: Iterable[str] = (),
    invoke: Callable[[str], Awaitable[str]] | None = None,
) -> JudgeResult:
    if invoke is None:
        if not (settings.deepseek_api_key or settings.qwen_api_key):
            raise JudgeUnavailable("未配置模型 Key")
        # judge 用主模型（reasoning）：fast 任务可能配置成另一个供应商，
        # 判定质量也更依赖推理能力
        model = get_chat_model("reasoning")

        async def model_invoke(prompt: str) -> str:
            return _text(await model.ainvoke(prompt))

        invoke = model_invoke

    try:
        raw = await invoke(build_prompt(question, reply, reference))
    except JudgeUnavailable:
        raise
    except Exception as exc:
        raise JudgeUnavailable(f"judge 调用失败: {str(exc)[:160]}") from exc
    return parse_judgement(raw)


def _text(message) -> str:
    content = getattr(message, "content", message)
    return content if isinstance(content, str) else str(content)


def aggregate(results: list[JudgeResult]) -> dict:
    n = len(results)
    solved = sum(1 for r in results if r.resolved)
    return {
        "judge_cases": n,
        "judge_resolved": solved,
        "judge_rate": round(solved / n, 3) if n else None,
    }
