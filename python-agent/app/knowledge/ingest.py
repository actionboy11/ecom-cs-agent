"""知识库索引构建 CLI：python -m app.knowledge.ingest --rebuild"""

from __future__ import annotations

import argparse
import json
import sys

from app.knowledge.policies import load_policies
from app.knowledge.store import build_store, index_policies

EXPECTED_POLICIES = 12


def main() -> None:
    parser = argparse.ArgumentParser(description="把售后政策写入 Chroma")
    parser.add_argument(
        "--rebuild", action="store_true", help="清空并重建索引（索引已存在时必须显式指定）"
    )
    args = parser.parse_args()

    policies = load_policies()
    if len(policies) != EXPECTED_POLICIES:
        # 解析异常时绝不动现有索引，避免把可用数据清空
        print(
            f"政策解析异常：期望 {EXPECTED_POLICIES} 条，实际 {len(policies)} 条，已中止",
            file=sys.stderr,
        )
        raise SystemExit(2)

    store = build_store()
    existing = store._collection.count()
    if existing and not args.rebuild:
        print(f"索引已存在 {existing} 条；如要重建请加 --rebuild", file=sys.stderr)
        raise SystemExit(2)

    count = index_policies(store, policies, reset=args.rebuild)
    print(json.dumps({"policies": count, "ids": [p.policy_id for p in policies]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
