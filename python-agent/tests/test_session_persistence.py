"""S3-1：会话状态持久化。

用 `aupdate_state` / `aget_state` 直接验证存储层，不触发节点逻辑（不依赖模型 Key）。
「重启」用关闭连接、重新打开同一个 SQLite 文件来模拟。
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from app.graph.builder import build_graph
from app.graph.checkpointer import sqlite_checkpointer


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
