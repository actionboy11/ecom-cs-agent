"""Streamlit 双栏工作台：左栏买家对话，右栏坐席审批与审计。

运行：
    streamlit run ui/app.py
环境变量：
    JAVA_BASE（默认 http://localhost:8080）
    AGENT_BASE（默认 http://localhost:8010）
"""

from __future__ import annotations

import os
import time

import streamlit as st

from api_client import WorkbenchApi, WorkbenchError

JAVA_BASE = os.getenv("JAVA_BASE", "http://localhost:8080")
AGENT_BASE = os.getenv("AGENT_BASE", "http://localhost:8010")


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
):
    st.session_state.setdefault(key, default)


def logout() -> None:
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.thread_id = None
    st.session_state.messages = []


def login_form() -> None:
    st.sidebar.title("登录")
    with st.sidebar.form("login"):
        username = st.text_input("用户名", value="buyer_a")
        password = st.text_input("密码", type="password", value="demo123")
        submitted = st.form_submit_button("登录")
    if submitted:
        try:
            result = api.login(username, password)
        except WorkbenchError:
            # 不区分「用户不存在」与「密码错误」
            st.sidebar.error("用户名或密码错误")
            return
        st.session_state.token = result["token"]
        st.session_state.user = result
        st.session_state.thread_id = f"ui-{username}-{int(time.time())}"
        st.session_state.messages = []
        st.rerun()


def render_chat() -> None:
    st.subheader("买家侧对话")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    text = st.text_input("输入问题", key="chat_input", placeholder="例如：CS2024001 到哪了")
    if st.button("发送", type="primary") and text.strip():
        st.session_state.messages.append({"role": "user", "content": text})
        try:
            reply = api.chat(st.session_state.token, st.session_state.thread_id, text)
            content = reply.get("reply", "")
            if reply.get("needs_human"):
                content += "\n\n_（已转人工，坐席可在右侧处理）_"
        except WorkbenchError as exc:
            content = f"调用失败：{exc}"
        st.session_state.messages.append({"role": "assistant", "content": content})
        st.rerun()


def render_agent_pane() -> None:
    st.subheader("坐席侧审批与审计")
    if st.session_state.user.get("role") != "CS_AGENT":
        st.info("当前账号不是坐席，审批与审计不可用。")
        return

    if st.button("刷新待办"):
        st.rerun()

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
        approved = st.radio("处理结果", ["通过", "驳回"], horizontal=True) == "通过"
        note = st.text_input("备注（可选）", key="review_note")
        if st.button("提交审批", type="primary"):
            try:
                api.review(st.session_state.token, labels[selected], approved, note)
                st.success("已提交，列表将刷新")
                st.rerun()
            except WorkbenchError as exc:
                st.error(f"审批失败：{exc}")

    with st.expander("最近审计", expanded=False):
        try:
            rows = api.audit(st.session_state.token, limit=20)
        except WorkbenchError as exc:
            st.error(f"审计加载失败：{exc}")
            rows = []
        if rows:
            st.dataframe(
                [
                    {
                        "时间": row.get("createdAt", ""),
                        "操作者": row.get("actor", ""),
                        "动作": row.get("action", ""),
                        "资源": row.get("resourceId", ""),
                        "结果": row.get("result", ""),
                    }
                    for row in rows
                ],
                use_container_width=True,
                hide_index=True,
            )


if st.session_state.token is None:
    login_form()
    st.title("电商售后客服工作台")
    st.caption("请先在左侧登录：买家账号看对话，坐席账号可审批售后。")
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
