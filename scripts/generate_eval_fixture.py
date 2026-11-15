"""生成 V9 评测 fixture：5 个用户、120 单，固定基准日 2026-11-15。

运行：python scripts/generate_eval_fixture.py
输出：java-service/src/main/resources/db/migration/V9__eval_fixture.sql
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from pathlib import Path

BASE = date(2026, 11, 15)
PRODUCTS = {
    "鞋": ("SKU1001", "轻量跑步鞋 42码", 399.00),
    "耳机": ("SKU1002", "主动降噪蓝牙耳机", 299.00),
    "行李箱": ("SKU1003", "20寸登机行李箱", 699.00),
    "杯子": ("SKU1004", "316 不锈钢保温杯", 129.00),
    "背包": ("SKU1005", "轻便双肩背包", 259.00),
    "充电宝": ("SKU1006", "20000mAh 充电宝", 199.00),
}
USERS = {
    "eval_a": (6, 28, {"鞋": 8, "耳机": 7, "行李箱": 3, "杯子": 3, "背包": 3, "充电宝": 4},
               {"待发货": 5, "运输中": 8, "已发货": 4, "已签收": 10, "已取消": 1}),
    "eval_b": (7, 26, {"鞋": 4, "耳机": 4, "行李箱": 7, "杯子": 7, "背包": 2, "充电宝": 2},
               {"待发货": 5, "运输中": 6, "已发货": 4, "已签收": 10, "已取消": 1}),
    "eval_c": (8, 24, {"鞋": 6, "耳机": 6, "行李箱": 4, "杯子": 4, "背包": 2, "充电宝": 2},
               {"待发货": 5, "运输中": 6, "已发货": 4, "已签收": 8, "已取消": 1}),
    "eval_d": (9, 22, {"鞋": 5, "耳机": 5, "行李箱": 3, "杯子": 3, "背包": 3, "充电宝": 3},
               {"待发货": 5, "运输中": 6, "已发货": 3, "已签收": 7, "已取消": 1}),
    "eval_e": (10, 20, {"鞋": 5, "耳机": 6, "行李箱": 3, "杯子": 3, "背包": 2, "充电宝": 1},
               {"待发货": 4, "运输中": 4, "已发货": 3, "已签收": 7, "已取消": 2}),
}


def offsets() -> list[int]:
    buckets = (
        [1, 2, 3] * 6
        + [4, 5, 6, 7] * 4 + [4, 5]
        + [8, 10, 12, 14] * 4 + [9, 11]
        + [16, 20, 25, 30] * 6
        + [35, 40, 50, 60] * 6
        + [70, 90] * 9
    )
    assert len(buckets) == 120, len(buckets)
    random.Random(20261115).shuffle(buckets)
    return buckets


def build() -> tuple[list[str], list[str], list[str], list[str]]:
    orders: list[dict] = []
    offset_pool = offsets()
    order_no = 201

    for username, (user_id, count, products, statuses) in USERS.items():
        product_seq: list[str] = []
        for product, qty in products.items():
            product_seq.extend([product] * qty)
        status_seq: list[str] = []
        for status, qty in statuses.items():
            status_seq.extend([status] * qty)
        assert len(product_seq) == count and len(status_seq) == count

        user_orders = []
        for index in range(count):
            product = product_seq[index]
            sku, name, price = PRODUCTS[product]
            created = BASE - timedelta(days=offset_pool[order_no - 201])
            if index > 0 and product_seq[index - 1] == product:
                created = min(created, user_orders[-1]["created"] + timedelta(days=1))
            user_orders.append(
                {
                    "order_no": f"CS2024{order_no:03d}",
                    "user_id": user_id,
                    "username": username,
                    "product": product,
                    "sku": sku,
                    "name": name,
                    "price": price,
                    "status": status_seq[index],
                    "created": created,
                    "tags": "",
                }
            )
            order_no += 1
        orders.extend(user_orders)

    for order in orders:
        if "delivered" not in order:
            order["delivered"] = (
                order["created"] + timedelta(days=3)
                if order["status"] == "已签收"
                else None
            )

    # 同商品同周：相邻重复商品，第二个日期贴近第一个
    for index in range(1, len(orders)):
        if orders[index]["product"] == orders[index - 1]["product"]:
            orders[index]["created"] = min(
                BASE - timedelta(days=1), orders[index - 1]["created"] + timedelta(days=1)
            )
            if orders[index]["delivered"] is not None:
                orders[index]["delivered"] = orders[index]["created"] + timedelta(days=3)

    # 12 个签收边界：6/7/8/14/15/16 天前各 2 单
    signed = [order for order in orders if order["status"] == "已签收"]
    boundaries = [6, 6, 7, 7, 8, 8, 14, 14, 15, 15, 16, 16]
    for order, days in zip(signed[-12:], boundaries):
        order["created"] = BASE - timedelta(days=days + 3)
        order["delivered"] = BASE - timedelta(days=days)

    # 4 个已签收但 delivered_at 缺失
    missing_delivered = [order for order in orders if order["delivered"] is not None][-4:]
    for order in missing_delivered:
        order["delivered"] = None

    # tags：gift 10、custom 8、gift+custom 2
    tagged = random.Random(7).sample(range(len(orders)), 20)
    for position, index in enumerate(tagged):
        if position < 10:
            orders[index]["tags"] = "gift"
        elif position < 18:
            orders[index]["tags"] = "custom"
        else:
            orders[index]["tags"] = "gift,custom"

    # 10 单无物流
    no_logistics = set(random.Random(11).sample(range(len(orders)), 10))

    # 12 单已有售后
    after_sales = random.Random(13).sample(
        [i for i, order in enumerate(orders) if order["status"] in ("已签收", "待发货")], 12
    )
    types = ["REFUND", "RETURN", "EXCHANGE", "URGE"]
    statuses_as = ["PENDING", "APPROVED", "REJECTED"]

    order_lines = []
    logistics_lines = []
    trace_lines = []
    after_lines = []
    for index, order in enumerate(orders):
        created = order["created"].strftime("%Y-%m-%d 10:00:00")
        delivered = (
            f"'{order['delivered'].strftime('%Y-%m-%d 15:00:00')}'"
            if order["delivered"]
            else "NULL"
        )
        tags = f"'{order['tags']}'" if order["tags"] else "NULL"
        order_lines.append(
            f"  ('{order['order_no']}', {order['user_id']}, '{order['sku']}', "
            f"'{order['name']}', {order['price']}, '{order['status']}', "
            f"'{created}', {delivered}, {tags})"
        )
        if index in no_logistics:
            continue
        carrier = ["顺丰速运", "中通快递", "京东物流", "圆通速递", "韵达快递"][index % 5]
        tracking = f"EV{order['order_no'][-7:]}"
        logistics_lines.append(
            f"  ('{order['order_no']}', '{carrier}', '{tracking}', '{order['status']}')"
        )
        if order["delivered"] is not None:
            trace_lines.append(
                f"  ('{order['order_no']}', 1, '{created}', '已揽收')"
            )
            trace_lines.append(
                f"  ('{order['order_no']}', 2, "
                f"'{order['delivered'].strftime('%Y-%m-%d 15:00:00')}', '已签收')"
            )

    for idx, order_index in enumerate(after_sales, start=1):
        order = orders[order_index]
        after_lines.append(
            f"  ('AS2026EVAL{idx:04d}', '{order['order_no']}', {order['user_id']}, "
            f"'{types[idx % 4]}', '评测预置售后', '{statuses_as[idx % 3]}', "
            f"'{order['created'].strftime('%Y-%m-%d 10:00:00')}')"
        )

    return order_lines, logistics_lines, trace_lines, after_lines


def main() -> None:
    order_lines, logistics_lines, trace_lines, after_lines = build()
    sql = [
        "-- V9: 评测 fixture（5 用户 × 120 单，固定基准日 2026-11-15）",
        "INSERT INTO users (id, username, password_hash, role, display_name) VALUES",
        "  (6, 'eval_a', '$2a$10$4THEoD8ZtbsDQAbiWTltLu5sGuGThiJRf8OspwjDCm0We8.VxB1IK', 'CUSTOMER', '评测A'),",
        "  (7, 'eval_b', '$2a$10$4THEoD8ZtbsDQAbiWTltLu5sGuGThiJRf8OspwjDCm0We8.VxB1IK', 'CUSTOMER', '评测B'),",
        "  (8, 'eval_c', '$2a$10$4THEoD8ZtbsDQAbiWTltLu5sGuGThiJRf8OspwjDCm0We8.VxB1IK', 'CUSTOMER', '评测C'),",
        "  (9, 'eval_d', '$2a$10$4THEoD8ZtbsDQAbiWTltLu5sGuGThiJRf8OspwjDCm0We8.VxB1IK', 'CUSTOMER', '评测D'),",
        "  (10, 'eval_e', '$2a$10$4THEoD8ZtbsDQAbiWTltLu5sGuGThiJRf8OspwjDCm0We8.VxB1IK', 'CUSTOMER', '评测E');",
        "",
        "INSERT INTO orders (order_no, user_id, sku, item_name, amount, status, created_at, delivered_at, tags) VALUES",
        ",\n".join(order_lines) + ";",
        "",
        "INSERT INTO logistics (order_no, carrier, tracking_no, status) VALUES",
        ",\n".join(logistics_lines) + ";",
        "",
        "INSERT INTO logistics_traces (order_no, seq, trace_time, content) VALUES",
        ",\n".join(trace_lines) + ";",
        "",
        "INSERT INTO after_sales_requests (request_no, order_no, user_id, type, reason, status, created_at) VALUES",
        ",\n".join(after_lines) + ";",
    ]
    path = (
        Path(__file__).resolve().parents[1]
        / "java-service/src/main/resources/db/migration/V9__eval_fixture.sql"
    )
    path.write_text("\n".join(sql), encoding="utf-8")
    print(f"wrote {path} orders={len(order_lines)} logistics={len(logistics_lines)} "
          f"traces={len(trace_lines)} after={len(after_lines)}")


if __name__ == "__main__":
    main()
