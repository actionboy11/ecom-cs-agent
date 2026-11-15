-- V8: 订单标签（赠品/定制），逗号分隔
ALTER TABLE orders
    ADD COLUMN tags VARCHAR(200) NULL AFTER delivered_at;
