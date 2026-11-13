"""轻量 Trace：每个节点写一行 JSONL，后续评测/W3 看板直接消费。

不依赖 LangSmith，原因：面试时要能讲清「trace 是怎么落地的」，
自建一版 60 行的实现比调第三方 SDK 更有说服力。
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.paths import resolve_trace_dir

TRACE_DIR = resolve_trace_dir()
TRACE_DIR.mkdir(parents=True, exist_ok=True)


def trace_event(thread_id: str, node: str, event: str, payload: dict[str, Any] | None = None) -> None:
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "thread_id": thread_id,
        "node": node,
        "event": event,
        "payload": payload or {},
    }
    path = TRACE_DIR / f"{time.strftime('%Y%m%d')}.jsonl"
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False) + "\n")


@contextmanager
def node_span(thread_id: str, node: str, **payload: Any) -> Iterator[dict[str, Any]]:
    """记录节点进出与耗时；异常也会被记录，便于复盘失败 case。"""
    started = time.perf_counter()
    trace_event(thread_id, node, "start", payload)
    info: dict[str, Any] = {}
    try:
        yield info
    except Exception as exc:
        trace_event(thread_id, node, "error", {"error": str(exc), **payload})
        raise
    finally:
        trace_event(
            thread_id,
            node,
            "end",
            {"elapsed_ms": round((time.perf_counter() - started) * 1000, 1), **info},
        )
