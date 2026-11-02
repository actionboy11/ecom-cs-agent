-- V1: 电商售后客服 Agent —— 业务数据库结构
-- 设计依据：docs/SPEC.md 第 5 节；docs/adr/0002（业务数据 MySQL）

CREATE TABLE users (
    id            BIGINT       NOT NULL AUTO_INCREMENT,
    username      VARCHAR(50)  NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    role          ENUM('CUSTOMER','CS_AGENT') NOT NULL,
    display_name  VARCHAR(50)  NOT NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_users_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE products (
    sku   VARCHAR(20)   NOT NULL,
    name  VARCHAR(100)  NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    attrs JSON          NULL,
    stock INT           NOT NULL DEFAULT 0,
    faq   JSON          NULL,
    PRIMARY KEY (sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE orders (
    order_no   VARCHAR(20)   NOT NULL,
    user_id    BIGINT        NOT NULL,
    sku        VARCHAR(20)   NOT NULL,
    item_name  VARCHAR(100)  NOT NULL,
    amount     DECIMAL(10,2) NOT NULL,
    status     VARCHAR(20)   NOT NULL,
    created_at DATETIME      NOT NULL,
    PRIMARY KEY (order_no),
    KEY idx_orders_user (user_id),
    CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users (id),
    CONSTRAINT fk_orders_sku  FOREIGN KEY (sku) REFERENCES products (sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE logistics (
    order_no    VARCHAR(20) NOT NULL,
    carrier     VARCHAR(50) NOT NULL,
    tracking_no VARCHAR(50) NOT NULL,
    status      VARCHAR(20) NOT NULL,
    PRIMARY KEY (order_no),
    CONSTRAINT fk_logistics_order FOREIGN KEY (order_no) REFERENCES orders (order_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE logistics_traces (
    id         BIGINT      NOT NULL AUTO_INCREMENT,
    order_no   VARCHAR(20) NOT NULL,
    seq        INT         NOT NULL,
    trace_time DATETIME    NOT NULL,
    content    VARCHAR(200) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_traces_order_seq (order_no, seq),
    CONSTRAINT fk_traces_order FOREIGN KEY (order_no) REFERENCES orders (order_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 审计：只记操作元数据，不记对话正文（ADR-0001 / ADR-0005）
CREATE TABLE audit_logs (
    id            BIGINT      NOT NULL AUTO_INCREMENT,
    ts            DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor         VARCHAR(50) NOT NULL,
    actor_role    VARCHAR(20) NOT NULL,
    action        VARCHAR(50) NOT NULL,
    resource_type VARCHAR(20) NOT NULL,
    resource_id   VARCHAR(50) NOT NULL,
    result        ENUM('OK','DENIED') NOT NULL,
    detail        JSON        NULL,
    PRIMARY KEY (id),
    KEY idx_audit_ts (ts),
    KEY idx_audit_actor (actor)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
