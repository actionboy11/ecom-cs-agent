-- V11: 运输中拦截记录
CREATE TABLE order_intercepts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_no VARCHAR(32) NOT NULL,
    user_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL,
    carrier VARCHAR(64) NULL,
    tracking_no VARCHAR(64) NULL,
    failure_reason VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_intercept_order (order_no),
    KEY idx_intercept_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
