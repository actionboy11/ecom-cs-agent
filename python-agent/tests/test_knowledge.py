"""S4-1：政策入库、全意图检索与引用。

分层验证：
- 解析与 CLI 接线（假 Chroma / 假向量）
- 真实 Chroma + 确定性假 embedding（不依赖 Ollama）
- 图行为：多轮、阈值、引用正文
"""

from __future__ import annotations

import re

import jwt
import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.config import settings
from app.graph.builder import build_graph
from app.knowledge import store as knowledge_store
from app.knowledge.policies import Policy, keyword_search, load_policies
from app.knowledge.store import MIN_SCORE, build_store, index_policies
from app.main import app
from tests.support import TEST_SECRET


class FakeEmbeddings(Embeddings):
    """确定性关键词计数向量：语义相近文本向量也相近。"""

    KEYWORDS = (
        "退款", "退货", "换货", "物流", "发票", "价保", "优惠券",
        "投诉", "配送", "签收", "质量", "七天", "运费", "超时", "到账",
    )

    def _vec(self, text: str) -> list[float]:
        # 二值而非计数：避免长文本靠词频堆分，保证重叠度可比
        return [1.0 if k in text else 0.0 for k in self.KEYWORDS]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


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
    """只验证 index_policies 的接线：先算向量、再清空、再写入。"""

    def __init__(self) -> None:
        self.ids: list[str] = []
        self.metas: list[dict] = []
        self.resets = 0
        self.embeddings = FakeEmbeddings()

    def reset_collection(self) -> None:
        self.resets += 1
        self.ids = []

    def add_texts(self, texts, metadatas, ids, embeddings=None) -> None:
        assert len(texts) == len(metadatas) == len(ids) == len(embeddings)
        self.ids = list(ids)
        self.metas = list(metadatas)


@pytest.fixture(autouse=True)
def _reset_store():
    yield
    knowledge_store.configure(None)


def test_policy_file_has_twelve_entries() -> None:
    policies = load_policies()
    assert len(policies) == 12
    assert [p.policy_id for p in policies] == [f"P{i:02d}" for i in range(1, 13)]
    assert all(p.title and p.body for p in policies)


def test_index_policies_writes_ids_and_titles() -> None:
    store = FakeChroma()
    assert index_policies(store) == 12
    assert store.ids == [f"P{i:02d}" for i in range(1, 13)]
    assert all(m.get("title") for m in store.metas)
    assert store.metas[2]["title"].startswith("退款")


def test_real_chroma_with_fake_embeddings_end_to_end(local_tmp) -> None:
    """真实 Chroma 落盘 + 假向量：验证「入库 → 检索」确实能命中 P03 且带标题。"""
    store = build_store(embeddings=FakeEmbeddings(), persist_directory=str(local_tmp / "chroma"))
    assert index_policies(store) == 12

    hits = store.similarity_search("退款多久到账", k=3)
    assert hits
    ids = [h.metadata["policy_id"] for h in hits]
    assert "P03" in ids
    assert hits[0].metadata["title"]


def test_keyword_fallback_finds_refund_policy() -> None:
    hits = keyword_search("退款到账要几个工作日", k=3)
    assert hits
    assert hits[0].policy_id == "P03"


def test_empty_index_falls_back_to_keywords() -> None:
    knowledge_store.configure(FakeStore([]))
    result = knowledge_store.retrieve("退款多久到账")
    assert result.source == "keyword"
    assert result.policy_refs == ["P03"]


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
    assert result.policy_refs == ["P03"]


def test_answer_contains_policy_citation_and_body(local_tmp, monkeypatch) -> None:
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
            json={"thread_id": "t-rag", "message": "退款到账要几个工作日"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        reply = resp.json()["reply"]
        assert "[P03]" in reply
        assert "1-3 个工作日" in reply, "引用必须来自 P03 正文，而不只是标了编号"


@pytest.mark.asyncio
async def test_policy_answer_not_masked_by_previous_tool_error(monkeypatch) -> None:
    """多轮：上一轮缺订单号的错误不能盖住本轮政策回答。"""
    monkeypatch.setattr(settings, "deepseek_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "deepseek_api_key", "test")
    monkeypatch.setattr(settings, "qwen_api_key", "test")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.5)

    knowledge_store.configure(FakeStore(load_policies()))
    graph = build_graph(MemorySaver())
    config = {"configurable": {"thread_id": "t-multi"}}

    await graph.ainvoke({"messages": [HumanMessage(content="我要退款")], "thread_id": "t-multi"}, config)
    second = await graph.ainvoke(
        {"messages": [HumanMessage(content="退货政策几天")], "thread_id": "t-multi"}, config
    )
    assert "请提供订单号" not in second["reply"]
    assert re.search(r"\[P0\d\]", second["reply"])


@pytest.mark.asyncio
async def test_retrieval_runs_for_non_policy_intent(monkeypatch) -> None:
    monkeypatch.setattr(settings, "deepseek_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "qwen_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "deepseek_api_key", "test")
    monkeypatch.setattr(settings, "qwen_api_key", "test")
    monkeypatch.setattr(settings, "llm_timeout_seconds", 0.5)

    from app.graph.nodes import respond_node

    knowledge_store.configure(FakeStore(load_policies()))
    out = await respond_node(
        {"messages": [HumanMessage(content="退款到账要几个工作日")], "intent": "other", "thread_id": "t-intent"}
    )
    assert out["policy_refs"], "非 policy 意图也应检索到政策引用"
