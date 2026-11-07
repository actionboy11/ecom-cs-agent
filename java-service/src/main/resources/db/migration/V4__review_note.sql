-- V4: 审批备注（SPEC §6.2 的 review 接口接受 note，需要落库，不能静默丢弃）
ALTER TABLE after_sales_requests
    ADD COLUMN review_note VARCHAR(200) NULL AFTER reviewed_at;
