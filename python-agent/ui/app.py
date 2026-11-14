"""售后调度台：单窗口工作台。

买家看到的就是一个对话窗口；坐席看到的是同一张卡片里的三个页签。
每个用户固定一个会话，登录时把历史消息拉回来。
"""

from __future__ import annotations

import os

import streamlit as st

try:  # 作为包导入（pytest / 其他模块）
    from ui import theme
    from ui.api_client import WorkbenchApi, WorkbenchError
    from ui.logic import can_review, format_reply, handoff_label, is_customer
except ImportError:  # streamlit run ui/app.py：脚本目录在 sys.path
    import theme
    from api_client import WorkbenchApi, WorkbenchError
    from logic import can_review, format_reply, handoff_label, is_customer

JAVA_BASE = os.getenv("JAVA_BASE", "http://localhost:8080")
AGENT_BASE = os.getenv("AGENT_BASE", "http://localhost:8000")

ROLE_LABELS = {"CUSTOMER": "买家", "CS_AGENT": "坐席"}


@st.cache_resource
def get_api() -> WorkbenchApi:
    return WorkbenchApi(JAVA_BASE, AGENT_BASE)


api = get_api()

st.set_page_config(page_title="售后调度台", layout="centered")
theme.inject()

for key, default in (
    ("token", None),
    ("user", None),
    ("thread_id", None),
    ("messages", []),
    ("notice", ""),
    ("chat_seq", 0),
):
    st.session_state.setdefault(key, default)


def role_label(role: str | None) -> str:
    return ROLE_LABELS.get((role or "").upper().removeprefix("ROLE_"), role or "访客")


def logout() -> None:
    for key, default in (
        ("token", None),
        ("user", None),
        ("thread_id", None),
        ("messages", []),
        ("notice", ""),
    ):
        st.session_state[key] = default


def load_history(token: str, thread_id: str) -> None:
    try:
        st.session_state.messages = api.thread_messages(token, thread_id)
    except WorkbenchError:
        st.session_state.messages = []


def login_page() -> None:
    with st.container(key="app_card"):
        theme.card_head(
            "售后调度台",
            "把每一单售后，落到具体的人手里。",
            "买家用它对话，坐席用它审批。",
        )
        with st.form("login"):
            username = st.text_input("用户名", value="buyer_a")
            password = st.text_input("密码", type="password")
            submitted = st.form_submit_button("登录", use_container_width=True)
        if submitted:
            try:
                result = api.login(username, password)
            except WorkbenchError:
                st.error("用户名或密码错误")
                return
            except Exception:  # noqa: BLE001
                st.error("无法连接业务系统")
                return
            st.session_state.token = result["token"]
            st.session_state.user = result
            # 一个用户只有一个会话：不按登录次数新建
            st.session_state.thread_id = f"ui-{username}"
            load_history(result["token"], st.session_state.thread_id)
            st.rerun()


def top_bar() -> None:
    user = st.session_state.user
    name = user.get("displayName") or user.get("role") or "用户"
    left, right = st.columns([6, 1])
    with left:
        st.markdown(
            f'<div class="who"><strong>{name}</strong> · {role_label(user.get("role"))}</div>',
            unsafe_allow_html=True,
        )
    with right:
        if st.button("退出", key="logout"):
            logout()
            st.rerun()


def send_message(text: str) -> None:
    st.session_state.messages.append({"role": "user", "content": text})
    try:
        reply = api.chat(st.session_state.token, st.session_state.thread_id, text)
        content = format_reply(reply)
    except WorkbenchError as exc:
        if "HTTP 401" in str(exc):
            logout()
            st.rerun()
        content = "刚才没连上服务，稍后再试一次。"
    st.session_state.messages.append({"role": "assistant", "content": content})
    st.session_state.chat_seq += 1


def after_sales_panel() -> None:
    try:
        mine = api.my_after_sales(st.session_state.token)
    except WorkbenchError as exc:
        st.error(f"售后加载失败：{exc}")
        return
    if not mine:
        st.caption("还没有售后请求。")
        return
    st.dataframe(
        [
            {
                "请求编号": row.get("requestNo", ""),
                "订单": row.get("orderNo", ""),
                "类型": row.get("type", ""),
                "状态": row.get("status", ""),
                "创建时间": row.get("createdAt", ""),
            }
            for row in mine[:50]
        ],
        width="stretch",
        hide_index=True,
    )


def chat_view() -> None:
    with st.container(key="app_card"):
        box = st.container()
        with box:
            if not st.session_state.messages:
                st.caption("直接问订单、物流或售后。")
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.write(message["content"])

        text = st.text_input(
            "输入问题",
            key=f"chat_input_{st.session_state.chat_seq}",
            placeholder="例如：CS2024001 到哪了",
            label_visibility="collapsed",
        )
        if st.button("发送", type="primary", use_container_width=True) and text.strip():
            send_message(text)
            st.rerun()

        if st.session_state.notice:
            st.success(st.session_state.notice)
            st.session_state.notice = ""

    if is_customer(st.session_state.user.get("role")):
        with st.expander("我的售后进度"):
            after_sales_panel()


def after_sales_tab() -> None:
    try:
        pending = api.pending_after_sales(st.session_state.token)
    except WorkbenchError as exc:
        st.error(f"待办加载失败：{exc}")
        return
    if not pending:
        st.caption("暂无待审批的售后申请。")
        return
    options = {
        f"{row['requestNo']} · {row['orderNo']} · {row['type']}": row["requestNo"]
        for row in pending
    }
    selected = st.selectbox("待办", list(options))
    request_no = options[selected]
    approved = st.radio("结果", ["通过", "驳回"], horizontal=True, key="as_result") == "通过"
    note = st.text_input("备注（驳回时必填）", key=f"as_note_{request_no}")
    if st.button("提交", type="primary", key="as_submit"):
        if not approved and not note.strip():
            st.error("驳回需要填写备注")
        else:
            try:
                api.review(st.session_state.token, request_no, approved, note)
                st.session_state.notice = "已提交"
                st.rerun()
            except WorkbenchError as exc:
                st.error(f"提交失败：{exc}")


def handoff_tab() -> None:
    try:
        handoffs = api.handoffs(st.session_state.token)
    except WorkbenchError as exc:
        st.error(f"待办加载失败：{exc}")
        return
    if handoffs:
        options = {
            f"{row['thread_id']} · {handoff_label(row.get('reason'))}": row["thread_id"]
            for row in handoffs
        }
        selected = st.selectbox("待恢复会话", list(options), key="handoff_select")
        thread_id = options[selected]
    else:
        st.caption("暂无转接待办。")
        thread_id = st.text_input("会话 ID", key="handoff_manual")

    approved = st.radio("结果", ["通过", "驳回"], horizontal=True, key=f"ho_result_{thread_id}") == "通过"
    note = st.text_input("备注", key=f"ho_note_{thread_id}")
    if st.button("恢复会话", type="primary", key="ho_submit"):
        if not thread_id.strip():
            st.error("请选择或填写会话 ID")
        else:
            try:
                api.resume(st.session_state.token, thread_id.strip(), approved, note)
                st.session_state.notice = "已恢复"
                st.rerun()
            except WorkbenchError as exc:
                st.error(f"恢复失败：{exc}")


def audit_tab() -> None:
    try:
        rows = api.audit(st.session_state.token, limit=20)
    except WorkbenchError as exc:
        st.error(f"审计加载失败：{exc}")
        return
    if not rows:
        st.caption("暂无审计记录。")
        return
    st.dataframe(
        [
            {
                "时间": row.get("ts", ""),
                "操作者": row.get("actor", ""),
                "动作": row.get("action", ""),
                "资源": row.get("resourceId", ""),
                "结果": row.get("result", ""),
            }
            for row in rows
        ],
        width="stretch",
        hide_index=True,
    )


def agent_view() -> None:
    with st.container(key="app_card"):
        theme.card_head("坐席侧", "工作台", "审批售后、处理转接待办、查看审计。")
        tabs = st.tabs(["售后审批", "转接待办", "审计"])
        with tabs[0]:
            after_sales_tab()
        with tabs[1]:
            handoff_tab()
        with tabs[2]:
            audit_tab()
        if st.session_state.notice:
            st.success(st.session_state.notice)
            st.session_state.notice = ""


if st.session_state.token is None:
    login_page()
    st.stop()

top_bar()
if can_review(st.session_state.user.get("role")):
    agent_view()
else:
    chat_view()
