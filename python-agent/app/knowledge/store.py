"""向量检索：Chroma（本地持久化）+ Ollama bge-m3，失败时退化为关键词检索。

对外只暴露 `retrieve()`：按 SPEC §8，检索发生在「生成回复之前」，
且只有相似度达到阈值（默认 0.35）的政策片段才进入上下文。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import settings
from app.knowledge.policies import Policy, keyword_search, load_policies
from app.paths import ensure_writable_temp, resolve_under_repo

logger = logging.getLogger(__name__)

COLLECTION = "policies"
MIN_SCORE = 0.35


def _ollama_host() -> str:
    """OllamaEmbeddings 需要主机名，不接受 OpenAI 兼容的 `/v1` 后缀。"""
    host = settings.ollama_base_url.rstrip("/")
    return host.removesuffix("/v1")


def default_embeddings() -> Any:
    """本地 Ollama 的 bge-m3（1024 维）。"""
    import os

    # 系统代理会劫持 localhost（表现为 502），这里显式放行
    for var in ("NO_PROXY", "no_proxy"):
        current = os.environ.get(var, "")
        if "127.0.0.1" not in current:
            os.environ[var] = ",".join(filter(None, [current, "localhost,127.0.0.1"]))

    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=settings.embedding_model, base_url=_ollama_host())


def build_store(embeddings: Any = None, persist_directory: str | Path | None = None) -> Any:
    """本地持久化 Chroma（Chroma 的 Rust SQLite 依赖可写的临时目录）。"""
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    from langchain_chroma import Chroma

    ensure_writable_temp()
    path = resolve_under_repo(persist_directory or settings.chroma_dir)
    Path(path).mkdir(parents=True, exist_ok=True)
    # 关闭遥测：受限网络下匿名上报会拖慢甚至阻塞查询
    client = chromadb.PersistentClient(
        path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
    )
    return Chroma(
        client=client,
        collection_name=COLLECTION,
        embedding_function=embeddings or default_embeddings(),
    )


def index_policies(
    store: Any, policies: list[Policy] | None = None, *, reset: bool = True
) -> int:
    """写入索引。`reset=True` 时先清空集合（重建语义）。

    先算 embedding 再清空：嵌入失败时不会把现有索引清成空库。
    """
    items = policies if policies is not None else load_policies()
    if not items:
        return 0

    texts = [f"{p.title}\n{p.body}" for p in items]  # 标题也参与向量，提升召回
    embeddings = store.embeddings.embed_documents(texts)
    if reset:
        store.reset_collection()
    store.add_texts(
        texts=texts,
        metadatas=[{"policy_id": p.policy_id, "title": p.title} for p in items],
        ids=[p.policy_id for p in items],
        embeddings=embeddings,
    )
    return len(items)


_store: Any = None
_store_failed_until: float = 0.0


def configure(store: Any) -> None:
    """测试或启动时注入已构建的向量库。"""
    global _store, _store_failed_until
    _store = store
    _store_failed_until = 0.0


def get_store() -> Any:
    global _store
    if _store is None:
        _store = build_store()
    return _store


def _from_document(doc: Any) -> Policy:
    return Policy(
        policy_id=str(doc.metadata.get("policy_id", "")),
        title=str(doc.metadata.get("title", "")),
        body=doc.page_content,
    )


@dataclass
class RetrievalResult:
    knowledge: str | None
    policy_refs: list[str]
    source: str  # vector / keyword / none


def retrieve(query: str, k: int = 3, min_score: float = MIN_SCORE) -> RetrievalResult:
    """按相关性阈值检索；不可用时退化关键词，仍无结果则返回空。"""
    global _store_failed_until
    if time.monotonic() < _store_failed_until:
        return _build(keyword_search(query, k), "keyword")

    try:
        store = get_store()
        if store._collection.count() == 0:
            return _build(keyword_search(query, k), "keyword")

        pairs = store.similarity_search_with_relevance_scores(query, k=k)
        kept = [(doc, float(score)) for doc, score in pairs if float(score) >= min_score]
        if not kept:
            logger.info("检索无命中（阈值 %.2f）: %s", min_score, query[:40])
            return RetrievalResult(None, [], "none")
        return _build([_from_document(doc) for doc, _ in kept], "vector")
    except Exception as exc:  # noqa: BLE001 - 检索不可用时不能拖垮对话
        # 失败后 60 秒内不再重试，避免每轮都卡在连不上的索引上
        _store_failed_until = time.monotonic() + 60
        logger.warning("向量检索不可用，退化为关键词: %s", str(exc)[:200])
        try:
            return _build(keyword_search(query, k), "keyword")
        except Exception:  # noqa: BLE001 - 兜底也失败时宁可没有知识
            return RetrievalResult(None, [], "none")


def _build(policies: list[Policy], source: str) -> RetrievalResult:
    if not policies:
        return RetrievalResult(None, [], "none")
    return RetrievalResult(
        knowledge="\n\n".join(p.as_document() for p in policies),
        # 引用只标首条（主依据），避免把 top-3 全部写成「依据」造成过度声称
        policy_refs=[policies[0].policy_id],
        source=source,
    )
