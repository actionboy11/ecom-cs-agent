"""售后调度台的视觉层：运单纸 + 邮路绿 + 印章。

设计方向（见 README/前端说明）：把工作台当成一张**调度运单**——
纸面是有灰绿的档案纸，分隔靠铅线而不是卡片阴影，强调色是邮路绿，
唯一的暖色是「印章朱」，只给越权/驳回这类需要人停一下的状态。

刻意避开：奶油底 + 陶土橙（生成式默认）、统一圆角卡片堆、全大写小标签。
"""

from __future__ import annotations

import streamlit as st

TOKENS = {
    "ink": "#16241F",
    "ink_soft": "#43564D",
    "paper": "#EEF1E9",
    "panel": "#F8FAF4",
    "line": "#C7D1C3",
    "green": "#1F5C4A",
    "green_deep": "#143F33",
    "blue": "#2B5C86",
    "seal": "#A6432E",
}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@600;700&display=swap');

:root {{
  --ink: {TOKENS["ink"]};
  --ink-soft: {TOKENS["ink_soft"]};
  --paper: {TOKENS["paper"]};
  --panel: {TOKENS["panel"]};
  --line: {TOKENS["line"]};
  --green: {TOKENS["green"]};
  --green-deep: {TOKENS["green_deep"]};
  --blue: {TOKENS["blue"]};
  --seal: {TOKENS["seal"]};
  --serif: "Noto Serif SC", "Source Han Serif SC", "Songti SC", serif;
  --sans: "Noto Sans SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
}}

html, body, [data-testid="stAppViewContainer"] {{
  background: var(--paper);
  color: var(--ink);
  font-family: var(--sans);
}}
[data-testid="stAppViewContainer"] > .main {{
  background-image: linear-gradient(180deg, rgba(31,92,74,.05), transparent 320px);
}}
header[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer,
[data-testid="stToolbar"], [data-testid="stAppDeployButton"],
[data-testid="stStatusWidget"] {{ display: none !important; }}
.block-container {{ padding-top: 2.2rem; max-width: 1180px; }}

h1, h2, h3, [data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 {{
  font-family: var(--serif);
  color: var(--ink);
  letter-spacing: .01em;
}}
p, li, label, [data-testid="stMarkdownContainer"] p {{ line-height: 1.7; }}

/* —— 运单头：整页唯一的高调元素 —— */
.waybill {{
  position: relative;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 2rem;
  padding: 1.4rem 1.6rem 1.3rem;
  margin-bottom: 1.6rem;
  background: var(--panel);
  border: 1px solid var(--line);
  border-left: 6px solid var(--green);
  border-radius: 2px;
}}
.waybill::after {{
  content: "";
  position: absolute;
  left: 1.6rem;
  right: 1.6rem;
  bottom: .55rem;
  border-bottom: 1px dashed var(--line);
}}
.waybill h1 {{
  font-size: clamp(1.5rem, 3.2vw, 2rem);
  line-height: 1.3;
  margin: .25rem 0 .15rem;
}}
.waybill .kicker {{
  font-size: .78rem;
  color: var(--ink-soft);
  letter-spacing: .18em;
}}
.waybill .lede {{ margin: 0; color: var(--ink-soft); font-size: .9rem; }}
.waybill .meta {{
  display: flex;
  gap: 1.8rem;
  padding-bottom: .35rem;
  text-align: right;
}}
.waybill .meta span {{ display: block; font-size: .72rem; color: var(--ink-soft); }}
.waybill .meta strong {{ font-size: .92rem; font-weight: 600; color: var(--ink); }}
.stamp {{
  display: inline-block;
  margin-top: .45rem;
  padding: .12rem .5rem;
  border: 1.5px solid var(--seal);
  border-radius: 2px;
  color: var(--seal);
  font-size: .74rem;
  letter-spacing: .12em;
  transform: rotate(-2deg);
}}

/* —— 侧栏：深绿墨块，像调度台压在纸上的垫板 —— */
[data-testid="stSidebar"] {{
  background: var(--green-deep);
  border-right: 1px solid #0e2f26;
}}
[data-testid="stSidebar"] * {{ color: #E9EFE6; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{ color: #F4F7F0; font-family: var(--serif); }}
[data-testid="stSidebar"] input {{
  background: var(--panel) !important;
  color: var(--ink) !important;
  border-radius: 3px !important;
}}
[data-testid="stSidebar"] [data-testid="stForm"] {{
  border: 1px solid rgba(233,239,230,.18);
  border-radius: 3px;
  padding: 1rem;
}}
[data-testid="stSidebar"] .stButton button {{
  background: transparent;
  border: 1px solid rgba(233,239,230,.45);
  color: #E9EFE6;
}}

/* —— 对话：像一张连续抄录的工单，不是聊天气泡墙 —— */
[data-testid="stChatMessage"] {{
  background: var(--panel) !important;
  border: 1px solid var(--line) !important;
  border-left: 3px solid var(--green) !important;
  border-radius: 4px;
  padding: .9rem 1rem;
  margin-bottom: .55rem;
  max-width: 82ch;
}}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
  background: var(--green-deep) !important;
  border-color: var(--green-deep) !important;
  border-left-color: var(--blue) !important;
}}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p {{ color: #F1F5EC !important; }}
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {{ display: none !important; }}
[data-testid="stChatMessageContent"] {{ width: 100%; }}

/* —— 控件：细线、小圆角、纸面 —— */
.stButton button, [data-testid="stFormSubmitButton"] button {{
  border-radius: 3px;
  font-weight: 600;
  letter-spacing: .02em;
  background: var(--green);
  color: #F7FAF2;
  border: 1px solid var(--green);
  transition: background .15s ease, transform .15s ease;
}}
.stButton button:hover, [data-testid="stFormSubmitButton"] button:hover {{
  background: var(--green-deep);
  border-color: var(--green-deep);
}}
.stButton button:active {{ transform: translateY(1px); }}
:focus-visible {{ outline: 2px solid var(--blue) !important; outline-offset: 2px !important; }}

[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-bottom: 2px solid var(--ink-soft);
  border-radius: 3px;
}}
[data-testid="stExpander"] {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 3px;
}}
[data-testid="stExpander"] summary {{
  font-family: var(--serif);
  font-weight: 600;
  color: var(--ink);
}}
[data-testid="stDataFrame"] {{
  border: 1px solid var(--line);
  border-radius: 3px;
}}
[data-testid="stMetricValue"] {{
  font-family: var(--serif);
  color: var(--green-deep);
}}
[data-testid="stAlertContainer"] {{
  background: var(--panel) !important;
  border: 1px solid var(--line) !important;
  border-left: 3px solid var(--blue) !important;
  border-radius: 3px !important;
  padding: .6rem .8rem !important;
  color: var(--ink) !important;
}}
[data-testid="stAlert"], [data-testid="stAlertContentInfo"] {{
  background: transparent !important;
  border: none !important;
  color: var(--ink) !important;
}}
[data-testid="stAlert"] * {{ color: var(--ink); }}

/* 一次页载入的轻抬升；尊重 prefers-reduced-motion */
@media (prefers-reduced-motion: no-preference) {{
  .block-container {{ animation: settle .28s ease-out both; }}
  @keyframes settle {{
    from {{ opacity: 0; transform: translateY(6px); }}
    to {{ opacity: 1; transform: none; }}
  }}
}}
@media (prefers-reduced-motion: reduce) {{
  * {{ animation: none !important; transition: none !important; }}
}}

@media (max-width: 760px) {{
  .waybill {{ flex-direction: column; align-items: flex-start; gap: .8rem; }}
  .waybill .meta {{ text-align: left; gap: 1.2rem; }}
}}
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def header(display_name: str, role_label: str, thread_id: str, stamp: str = "") -> None:
    safe_thread = thread_id[-12:] if thread_id else "—"
    stamp_html = f'<span class="stamp">{stamp}</span>' if stamp else ""
    st.markdown(
        f"""
        <div class="waybill">
          <div>
            <div class="kicker">售后调度台</div>
            <h1>把每一单售后，落到具体的人手里。</h1>
            <p class="lede">买家对话、坐席审批与审计在同一张单上流转。</p>
            {stamp_html}
          </div>
          <div class="meta">
            <div><span>当前身份</span><strong>{display_name} · {role_label}</strong></div>
            <div><span>会话</span><strong>{safe_thread}</strong></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
