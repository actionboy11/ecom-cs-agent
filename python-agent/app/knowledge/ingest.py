"""知识库索引构建 CLI：python -m app.knowledge.ingest --rebuild"""

from __future__ import annotations

import argparse
import json

from app.knowledge.policies import load_policies
from app.knowledge.store import build_store, index_policies


def main() -> None:
    parser = argparse.ArgumentParser(description="把售后政策写入 Chroma")
    parser.add_argument("--rebuild", action="store_true", help="清空并重建索引（默认也是重建）")
    args = parser.parse_args()

    policies = load_policies()
    store = build_store()
    count = index_policies(store, policies)
    print(json.dumps({"policies": count, "ids": [p.policy_id for p in policies]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
