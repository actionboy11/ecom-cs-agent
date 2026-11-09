"""S4-1：政策入库、检索与引用。

测试用确定性替身（关键词向量 / 内存向量库），不依赖 Chroma 服务与本地 Ollama；
真实链路由 docker compose 的 chromadb + bge-m3 承担。
"""

from __future__ import annotations

import re

import jwt
import pytest
from langchain_core.documents import Document

from app.config import settings
from app.knowledge import store as knowledge_store
from app.knowledge.policies import Policy, keyword_search, load_policies
from app.knowledge.store import index_policies
from app.main import app
from tests.support import TEST_SECRET


class FakeStore:
    """内存向量库：检索直接复用关键词排序，保证断言确定性。"""

    def __init__(self, policies: list[Policy]) -> None:
        self.policies = policies
        self._collection = self

    def count(self) -> int:
        return len(self.policies)

    def similarity_search(self, query: str, k: int = 3) -> list[Document]:
        return [
            Document(page_content=p.body, metadata={"policy_id": p.policy_id, "title": p.title})
            for p in keyword_search(query, k, self.policies)
        ]


class FakeChroma:
    """只验证 index_policies 的接线：清空 → 写入 12 条。"""

    def __init__(self) -> None:
        self.ids: list[str] = []

    def reset_collection(self) -> None:
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


def test_keyword_fallback_finds_refund_policy() -> None:
    hits = keyword_search("退款到账要几个工作日", k=3)
    assert hits
    assert hits[0].policy_id == "P03"


def test_store_failure_falls_back_to_keywords() -> None:
    class BrokenStore:
        class _collection:
            @staticmethod
            def count() -> int:
                return 1

        _collection = _collection()

        def similarity_search(self, *_args, **_kwargs):
            raise RuntimeError("chroma down")

    knowledge_store.configure(BrokenStore())
    hits = knowledge_store.search("退款多久到账", k=3)
    assert hits and hits[0].policy_id == "P03"


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
