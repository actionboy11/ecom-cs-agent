"""向量检索：Chroma（本地持久化）+ Ollama bge-m3，失败时退化为关键词检索。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.config import settings
from app.knowledge.policies import Policy, keyword_search, load_policies
from app.paths import ensure_writable_temp, resolve_under_repo

logger = logging.getLogger(__name__)

COLLECTION = "policies"


def _ollama_host() -> str:
    """OllamaEmbeddings 需要主机名，不接受 OpenAI 兼容的 `/v1` 后缀。"""
    host = settings.ollama_base_url.rstrip("/")
    return host[:-3] if host.endswith("/v1") else host


def default_embeddings() -> Any:
    """本地 Ollama 的 bge-m3（1024 维）。"""
    import os

    # 系统代理会劫持 localhost（表现为 502），这里显式放行
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
    os.environ.setdefault("no_proxy", "localhost,127.0.0.1")

    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=settings.embedding_model, base_url=_ollama_host())


def build_store(embeddings: Any = None, persist_directory: str | Path | None = None) -> Any:
    """本地持久化 Chroma。

    注意：Chroma 的 Rust SQLite 依赖可写的临时目录，因此先修正 TMP/TEMP。
    """
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    from langchain_chroma import Chroma

    ensure_writable_temp()
    path = resolve_under_repo(persist_directory or settings.chroma_dir)
    Path(path).mkdir(parents=True, exist_ok=True)
    # 关闭遥测：内网/受限网络下匿名上报会拖慢甚至阻塞启动与查询
    client = chromadb.PersistentClient(
        path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
    )
    return Chroma(
        client=client,
        collection_name=COLLECTION,
        embedding_function=embeddings or default_embeddings(),
    )


def index_policies(store: Any, policies: list[Policy] | None = None) -> int:
    """重建索引：先清空集合，再写入，保证可重复执行。"""
    items = policies if policies is not None else load_policies()
    store.reset_collection()
    if not items:
        return 0
    store.add_texts(
        texts=[p.body for p in items],
        metadatas=[{"policy_id": p.policy_id, "title": p.title} for p in items],
        ids=[p.policy_id for p in items],
    )
    return len(items)


_store: Any = None


def configure(store: Any) -> None:
    """测试或启动时注入已构建的向量库。"""
    global _store
    _store = store


def get_store() -> Any:
    global _store
    if _store is None:
        _store = build_store()
    return _store


def search(query: str, k: int = 3) -> list[Policy]:
    """先走向量检索；任何失败（Chroma/Ollama 不可用、索引为空）都退化为关键词。"""
    try:
        store = get_store()
        if store._collection.count() == 0:  # noqa: SLF001 - langchain-chroma 无公开计数接口
            return keyword_search(query, k)
        hits = store.similarity_search(query, k=k)
        found = [
            Policy(
                policy_id=str(doc.metadata.get("policy_id", "")),
                title=str(doc.metadata.get("title", "")),
                body=doc.page_content,
            )
            for doc in hits
            if doc.metadata.get("policy_id")
        ]
        return found or keyword_search(query, k)
    except Exception as exc:  # noqa: BLE001 - 检索不可用时不能拖垮对话
        logger.warning("向量检索不可用，退化为关键词: %s", str(exc)[:200])
        return keyword_search(query, k)
