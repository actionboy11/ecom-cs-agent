-- V6: 订单签收时间（用于「昨天收到」这类时间指代）
ALTER TABLE orders
    ADD COLUMN delivered_at DATETIME NULL AFTER created_at;

-- 从物流轨迹中最新一条「已签收」回填；未签收保持 NULL
UPDATE orders o
JOIN (
    SELECT order_no, MAX(trace_time) AS ts
    FROM logistics_traces
    WHERE content = '已签收'
    GROUP BY order_no
) t ON t.order_no = o.order_no
SET o.delivered_at = t.ts;

CREATE INDEX idx_orders_user_created ON orders (user_id, created_at);
