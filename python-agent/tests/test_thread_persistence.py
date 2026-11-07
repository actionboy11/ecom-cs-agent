"""S3-1：会话状态持久化。

两组证据：
1. 存储层：`aupdate_state` / `aget_state` 直接验证 SQLite round-trip 与 thread 隔离（不触发节点）。
2. 真实链路：三轮 `ainvoke`，中间关闭连接模拟重启，验证对话上下文确实延续。

真实链路测试把模型 base_url 指向不可达地址并调小超时，让节点走关键词兜底与模板回复，
因此不需要 API Key、不需要 Java 服务、也不会真的等 60 秒。
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from app.config import settings
from app.graph.builder import build_graph
from app.graph.checkpointer import sqlite_checkpointer


def _force_offline(monkeypatch) -> None:
    monkeypatch.setattr(settings, "deepseek_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "qwen_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "deepseek_api_key", "test")
    monkeypatch.setattr(settings, "qwen_api_key", "test")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.5)


@pytest.mark.asyncio
async def test_three_turns_survive_a_restart(tmp_path, monkeypatch) -> None:
    _force_offline(monkeypatch)
    db_path = str(tmp_path / "state.db")
    config = {"configurable": {"thread_id": "t-flow"}}

    async with sqlite_checkpointer(db_path) as saver:
        graph = build_graph(saver)
        await graph.ainvoke({"messages": [HumanMessage(content="退货政策几天")], "thread_id": "t-flow"}, config)
        await graph.ainvoke({"messages": [HumanMessage(content="那质量问题呢")], "thread_id": "t-flow"}, config)

    # 关闭连接 = 进程重启；同一个 thread 发第三轮
    async with sqlite_checkpointer(db_path) as saver:
        graph = build_graph(saver)
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="谢谢")], "thread_id": "t-flow"}, config
        )
        messages = result["messages"]
        assert len(messages) >= 5, "三轮对话应累积至少 5 条消息（3 用户 + 2 以上回复）"
        contents = [m.content for m in messages if isinstance(m, HumanMessage)]
        assert any("退货政策" in c for c in contents), "重启前第一轮的内容必须还在上下文里"


@pytest.mark.asyncio
async def test_state_survives_a_new_graph_instance(tmp_path) -> None:
    db_path = str(tmp_path / "state.db")
    config = {"configurable": {"thread_id": "t-persist"}}

    async with sqlite_checkpointer(db_path) as saver:
        graph = build_graph(saver)
        await graph.aupdate_state(config, {"messages": [HumanMessage(content="第一条：订单 CS2024001")]})

    # 关闭连接 = 进程重启；重新打开同一个库
    async with sqlite_checkpointer(db_path) as saver:
        graph = build_graph(saver)
        snapshot = await graph.aget_state(config)
        messages = snapshot.values.get("messages", [])
        assert messages, "重启后应能读到之前的消息"
        assert messages[-1].content == "第一条：订单 CS2024001"


@pytest.mark.asyncio
async def test_threads_do_not_share_state(tmp_path) -> None:
    db_path = str(tmp_path / "state.db")

    async with sqlite_checkpointer(db_path) as saver:
        graph = build_graph(saver)
        await graph.aupdate_state(
            {"configurable": {"thread_id": "t-a"}}, {"messages": [HumanMessage(content="A 的消息")]}
        )
        await graph.aupdate_state(
            {"configurable": {"thread_id": "t-b"}}, {"messages": [HumanMessage(content="B 的消息")]}
        )

        a = await graph.aget_state({"configurable": {"thread_id": "t-a"}})
        b = await graph.aget_state({"configurable": {"thread_id": "t-b"}})

        assert a.values["messages"][-1].content == "A 的消息"
        assert b.values["messages"][-1].content == "B 的消息"


@pytest.mark.asyncio
async def test_unknown_thread_has_no_state(tmp_path) -> None:
    db_path = str(tmp_path / "state.db")
    async with sqlite_checkpointer(db_path) as saver:
        graph = build_graph(saver)
        snapshot = await graph.aget_state({"configurable": {"thread_id": "never-seen"}})
        assert snapshot.values.get("messages", []) == []


def test_graph_requires_initialization() -> None:
    """未经过 lifespan 就拿图，必须报错而不是悄悄退回内存实现。"""
    from app.graph.builder import get_graph, reset_graph

    reset_graph()
    with pytest.raises(RuntimeError):
        get_graph()


def test_relative_db_path_resolves_to_repo_root() -> None:
    from app.graph.checkpointer import REPO_ROOT, resolve_db_path

    resolved = resolve_db_path("data/agent_state.db")
    assert resolved.is_absolute()
    assert resolved == REPO_ROOT / "data" / "agent_state.db"
