-- V5: 催件加入售后类型（URGE），与退款/退货/换货共用一张表与审批流
ALTER TABLE after_sales_requests
    MODIFY type ENUM('REFUND','RETURN','EXCHANGE','URGE') NOT NULL;
