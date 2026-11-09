package com.example.csagent.mcp;

/** 缺少必填槽位：映射为 MISSING_SLOT 而非「订单不存在」。 */
public class MissingSlotException extends RuntimeException {
    public MissingSlotException(String message) {
        super(message);
    }
}
