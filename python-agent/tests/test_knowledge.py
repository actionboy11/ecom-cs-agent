"""S4-1：政策入库、全意图检索与引用。

测试用确定性替身（关键词排序 / 内存向量库），不依赖 Chroma 与本地 Ollama；
真实链路由本地 Chroma + bge-m3 承担。
"""

from __future__ import annotations

import re

import jwt
import pytest
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

from app.config import settings
from app.graph.builder import build_graph  # noqa: F401 - 保持图装配的导入路径可用
from app.knowledge import store as knowledge_store
from app.knowledge.policies import Policy, keyword_search, load_policies
from app.knowledge.store import MIN_SCORE, index_policies
from app.main import app
from tests.support import TEST_SECRET


class FakeStore:
    """内存向量库：检索复用关键词排序，分数固定为 0.9（高于阈值）。"""

    def __init__(self, policies: list[Policy], score: float = 0.9) -> None:
        self.policies = policies
        self.score = score
        self._collection = self

    def count(self) -> int:
        return len(self.policies)

    def similarity_search_with_relevance_scores(self, query: str, k: int = 3):
        return [
            (Document(page_content=p.body, metadata={"policy_id": p.policy_id, "title": p.title}), self.score)
            for p in keyword_search(query, k, self.policies)
        ]


class FakeChroma:
    def __init__(self) -> None:
        self.ids: list[str] = []
        self.resets = 0

    def reset_collection(self) -> None:
        self.resets += 1
        self.ids = []

    def add_texts(self, texts, metadatas, ids) -> None:
        assert len(texts) == len(metadatas) == len(ids)
        self.ids = list(ids)


@pytest.fixture(autouse=True)
def _reset_store():
    yield
    knowledge_store.configure(None)


def test_policy_file_has_twelve_entries() -> None:
    policies = load_policies()
    assert len(policies) == 12
    assert [p.policy_id for p in policies] == [f"P{i:02d}" for i in range(1, 13)]
    assert all(p.title and p.body for p in policies)


def test_index_policies_writes_all_entries() -> None:
    store = FakeChroma()
    assert index_policies(store) == 12
    assert store.ids == [f"P{i:02d}" for i in range(1, 13)]
    assert store.resets == 1


def test_keyword_fallback_finds_refund_policy() -> None:
    hits = keyword_search("退款到账要几个工作日", k=3)
    assert hits
    assert hits[0].policy_id == "P03"


def test_low_relevance_is_filtered_out() -> None:
    knowledge_store.configure(FakeStore(load_policies(), score=MIN_SCORE - 0.1))
    result = knowledge_store.retrieve("退款多久到账")
    assert result.source == "none"
    assert result.knowledge is None
    assert result.policy_refs == []


def test_store_failure_falls_back_to_keywords() -> None:
    class BrokenStore:
        class _collection:
            @staticmethod
            def count() -> int:
                return 1

        _collection = _collection()

        def similarity_search_with_relevance_scores(self, *_args, **_kwargs):
            raise RuntimeError("chroma down")

    knowledge_store.configure(BrokenStore())
    result = knowledge_store.retrieve("退款多久到账", k=3)
    assert result.source == "keyword"
    assert result.policy_refs[0] == "P03"


def test_answer_contains_policy_citation(local_tmp, monkeypatch) -> None:
    monkeypatch.setattr(settings, "deepseek_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "qwen_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "deepseek_api_key", "test")
    monkeypatch.setattr(settings, "qwen_api_key", "test")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.5)
    monkeypatch.setattr(settings, "jwt_secret", TEST_SECRET)
    monkeypatch.setattr(settings, "agent_state_db", str(local_tmp / "state.db"))

    knowledge_store.configure(FakeStore(load_policies()))

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        token = jwt.encode(
            {"sub": "buyer_a", "userId": 1, "role": "CUSTOMER", "exp": 9999999999},
            TEST_SECRET,
            algorithm="HS256",
        )
        resp = client.post(
            "/api/v1/chat",
            json={"thread_id": "t-rag", "message": "退货政策里退款一般多久到账"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        reply = resp.json()["reply"]
        assert re.search(r"\[P0\d\]", reply), reply
        assert "P03" in reply


@pytest.mark.asyncio
async def test_retrieval_runs_for_non_policy_intent(monkeypatch) -> None:
    """SPEC §8：全意图检索——非 policy 意图也要先检索，而不是只有 policy 才检索。"""
    monkeypatch.setattr(settings, "deepseek_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "qwen_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "deepseek_api_key", "test")
    monkeypatch.setattr(settings, "qwen_api_key", "test")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.5)

    from app.graph.nodes import respond_node

    knowledge_store.configure(FakeStore(load_policies()))
    out = await respond_node(
        {
            "messages": [HumanMessage(content="退款多久到账")],
            "intent": "other",
            "thread_id": "t-intent",
        }
    )
    assert out["policy_refs"], "非 policy 意图也应检索到政策引用"
