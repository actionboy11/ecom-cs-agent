"""Streamlit 双栏工作台：左栏买家对话，右栏坐席审批与审计。

运行（在 python-agent/ 目录下）：
    streamlit run ui/app.py
环境变量：
    JAVA_BASE（默认 http://localhost:8080）
    AGENT_BASE（默认 http://localhost:8000；本地 uvicorn 用 8010）
"""

from __future__ import annotations

import os
import uuid

import streamlit as st

try:  # 作为包导入（pytest / 其他模块）
    from ui.api_client import WorkbenchApi, WorkbenchError
    from ui.logic import audit_row, can_review, format_reply
except ImportError:  # streamlit run ui/app.py：脚本目录在 sys.path
    from api_client import WorkbenchApi, WorkbenchError
    from logic import audit_row, can_review, format_reply

JAVA_BASE = os.getenv("JAVA_BASE", "http://localhost:8080")
AGENT_BASE = os.getenv("AGENT_BASE", "http://localhost:8000")


@st.cache_resource
def get_api() -> WorkbenchApi:
    return WorkbenchApi(JAVA_BASE, AGENT_BASE)


api = get_api()

st.set_page_config(page_title="电商售后客服工作台", layout="wide")

for key, default in (
    ("token", None),
    ("user", None),
    ("thread_id", None),
    ("messages", []),
    ("notice", ""),
    ("chat_seq", 0),
):
    st.session_state.setdefault(key, default)


def logout() -> None:
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.thread_id = None
    st.session_state.messages = []
    st.session_state.notice = ""


def expired() -> None:
    """令牌过期：清空登录态并提示重新登录。"""
    logout()
    st.session_state.notice = "登录已过期，请重新登录"
    st.rerun()


def login_form() -> None:
    st.sidebar.title("登录")
    with st.sidebar.form("login"):
        username = st.text_input("用户名", value="buyer_a")
        password = st.text_input("密码", type="password", placeholder="演示密码见 README")
        submitted = st.form_submit_button("登录")
    if submitted:
        try:
            result = api.login(username, password)
        except WorkbenchError:
            # 不区分「用户不存在」与「密码错误」
            st.sidebar.error("用户名或密码错误")
            return
        except Exception:  # noqa: BLE001 - 后端不可用/网络故障
            st.sidebar.error("无法连接业务系统，请确认 Java 服务已启动")
            return
        st.session_state.token = result["token"]
        st.session_state.user = result
        st.session_state.thread_id = f"ui-{username}-{uuid.uuid4().hex[:12]}"
        st.session_state.messages = []
        st.rerun()


def render_chat() -> None:
    st.subheader("买家侧对话")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # key 带序号：每次发送后换 key，输入框自动清空，避免重复发送同一句
    text = st.text_input("输入问题", key=f"chat_input_{st.session_state.chat_seq}")
    if st.button("发送", type="primary") and text.strip():
        st.session_state.messages.append({"role": "user", "content": text})
        try:
            reply = api.chat(st.session_state.token, st.session_state.thread_id, text)
            content = format_reply(reply)
        except WorkbenchError as exc:
            if "HTTP 401" in str(exc):
                expired()
            content = f"调用失败：{exc}"
        except Exception:  # noqa: BLE001
            content = "调用失败：无法连接 Agent 服务"
        st.session_state.messages.append({"role": "assistant", "content": content})
        st.session_state.chat_seq += 1
        st.rerun()


def render_agent_pane() -> None:
    st.subheader("坐席侧审批与审计")
    if not can_review(st.session_state.user.get("role")):
        st.info("当前账号不是坐席，审批与审计不可用。")
        return

    if st.session_state.notice:
        st.success(st.session_state.notice)
        st.session_state.notice = ""

    try:
        pending = api.pending_after_sales(st.session_state.token)
    except WorkbenchError as exc:
        st.error(f"待办加载失败：{exc}")
        pending = []

    if not pending:
        st.caption("暂无待审批的售后申请")
    else:
        labels = {
            f"{row['requestNo']} · {row['orderNo']} · {row['type']}": row["requestNo"]
            for row in pending
        }
        selected = st.selectbox("待办", list(labels))
        request_no = labels[selected]
        approved = st.radio("售后审批结果", ["通过", "驳回"], horizontal=True) == "通过"
        # key 绑定到具体申请，切换待办时备注不会串到另一条
        note = st.text_input("备注（驳回时必填）", key=f"review_note_{request_no}")
        if st.button("提交审批", type="primary"):
            if not approved and not note.strip():
                st.error("驳回需要填写备注")
            else:
                try:
                    api.review(st.session_state.token, request_no, approved, note)
                    st.session_state.notice = "已提交审批，列表已刷新"
                    st.rerun()
                except WorkbenchError as exc:
                    st.error(f"审批失败：{exc}")

    with st.expander("恢复转接会话", expanded=False):
        handoff_thread = st.text_input("会话 ID", key="handoff_thread")
        handoff_approved = st.radio(
            "转接审批结果", ["通过", "驳回"], horizontal=True, key="handoff_result"
        ) == "通过"
        handoff_note = st.text_input("审批备注", key="handoff_note")
        if st.button("恢复会话", key="handoff_submit"):
            if not handoff_thread.strip():
                st.error("请填写会话 ID")
            else:
                try:
                    reply = api.resume(
                        st.session_state.token,
                        handoff_thread.strip(),
                        handoff_approved,
                        handoff_note,
                    )
                    st.session_state.notice = f"转接会话已恢复（{'通过' if handoff_approved else '驳回'}）"
                    st.rerun()
                except WorkbenchError as exc:
                    st.error(f"恢复失败：{exc}")

    with st.expander("最近审计", expanded=False):
        try:
            rows = api.audit(st.session_state.token, limit=20)
        except WorkbenchError as exc:
            st.error(f"审计加载失败：{exc}")
            rows = []
        if rows:
            denied = sum(1 for row in rows if row.get("result") == "DENIED")
            st.metric("累计拦截越权（最近 100 条内）", denied)
            st.dataframe(
                [audit_row(row) for row in rows],
                width="stretch",
                hide_index=True,
            )


if st.session_state.token is None:
    login_form()
    st.title("电商售后客服工作台")
    st.caption("请先在左侧登录：买家账号看对话，坐席账号可审批售后。")
    if st.session_state.notice:
        st.info(st.session_state.notice)
else:
    user = st.session_state.user
    st.sidebar.success(f"{user.get('displayName')}（{user.get('role')}）")
    if st.sidebar.button("退出登录"):
        logout()
        st.rerun()

    left, right = st.columns([3, 2])
    with left:
        render_chat()
    with right:
        render_agent_pane()
