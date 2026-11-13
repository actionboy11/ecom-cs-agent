"""S7-1：工作台纯逻辑（角色门禁、回复拼装、审计行）。"""

from __future__ import annotations

from ui.logic import audit_row, can_review, format_reply


def test_only_agent_can_review() -> None:
    assert can_review("CS_AGENT") is True
    assert can_review("ROLE_CS_AGENT") is True
    assert can_review("cs_agent") is True
    assert can_review("CUSTOMER") is False
    assert can_review(None) is False


def test_format_reply_appends_transfer_hint() -> None:
    assert format_reply({"reply": "已查询", "needs_human": False}) == "已查询"
    text = format_reply({"reply": "已转接", "needs_human": True})
    assert "已转接" in text and "转接人工" in text
    # 买家没有审批权，提示只能是「等待处理」，不能写「可在右侧处理」
    assert "等待处理" in text
    assert "右侧" not in text


def test_format_reply_handles_empty_reply() -> None:
    assert format_reply({}) == ""
    assert format_reply({"reply": None, "needs_human": True}).startswith("\n\n_（已转接人工")


def test_audit_row_uses_java_ts_field() -> None:
    row = audit_row(
        {
            "ts": "2026-11-13T20:00:00",
            "actor": "cs_agent",
            "action": "LOGIN",
            "resourceId": "cs_agent",
            "result": "OK",
        }
    )
    assert row["时间"] == "2026-11-13T20:00:00"
    assert row["动作"] == "LOGIN"
    assert row["结果"] == "OK"
