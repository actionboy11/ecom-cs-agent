-- V3: 售后请求统一建模（取代内存退款实现）
-- 三类售后共用一张表；本切片只落 REFUND，类型扩展在 S2-2。

CREATE TABLE after_sales_requests (
    request_no  VARCHAR(20)  NOT NULL,
    order_no    VARCHAR(20)  NOT NULL,
    user_id     BIGINT       NOT NULL,
    type        ENUM('REFUND','RETURN','EXCHANGE') NOT NULL,
    reason      VARCHAR(200) NULL,
    status      ENUM('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'PENDING',
    created_at  DATETIME     NOT NULL,
    reviewed_by VARCHAR(50)  NULL,
    reviewed_at DATETIME     NULL,
    PRIMARY KEY (request_no),
    KEY idx_as_user (user_id),
    KEY idx_as_order (order_no),
    CONSTRAINT fk_as_order FOREIGN KEY (order_no) REFERENCES orders (order_no),
    CONSTRAINT fk_as_user  FOREIGN KEY (user_id)  REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 一条待审记录，供坐席审批演示与测试使用（订单 CS2024003 属于 buyer_a）
INSERT INTO after_sales_requests (request_no, order_no, user_id, type, reason, status, created_at)
VALUES ('AS20261101000001', 'CS2024003', 1, 'REFUND', '尺码不合适', 'PENDING', '2026-11-01 15:00:00');
