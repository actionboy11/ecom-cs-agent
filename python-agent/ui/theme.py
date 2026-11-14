"""售后调度台的视觉层：运单纸 + 邮路绿 + 印章。

单窗口工作台：一个居中的对话卡片，不再分栏、不再显示无关提示。
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
header[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer,
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stToolbar"], [data-testid="stAppDeployButton"],
[data-testid="stStatusWidget"] {{ display: none !important; }}

.block-container {{
  max-width: 780px;
  padding: 2.6rem 1.2rem 3rem;
}}

h1, h2, h3 {{ font-family: var(--serif); color: var(--ink); }}
p, li, label {{ line-height: 1.7; }}

/* 一整张单：登录、对话、坐席台都落在这张纸卡上 */
.st-key-app_card {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-left: 4px solid var(--green);
  border-radius: 4px;
  padding: 1.5rem 1.6rem 1.4rem;
}}
.card-kicker {{
  font-size: .76rem;
  letter-spacing: .16em;
  color: var(--ink-soft);
}}
.card-title {{
  font-family: var(--serif);
  font-size: 1.55rem;
  line-height: 1.4;
  margin: .3rem 0 .2rem;
}}
.card-sub {{ color: var(--ink-soft); font-size: .88rem; margin: 0 0 .6rem; }}

/* 对话：连续工单，不是气泡墙 */
[data-testid="stChatMessage"] {{
  background: transparent !important;
  border: none !important;
  border-left: 2px solid var(--line) !important;
  border-radius: 0 !important;
  padding: .35rem 0 .35rem .9rem !important;
  margin-bottom: .4rem;
}}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{
  border-left: 2px solid var(--green) !important;
}}
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {{ display: none !important; }}
[data-testid="stChatMessageContent"] {{ width: 100%; }}

/* 控件 */
.stButton button, [data-testid="stFormSubmitButton"] button {{
  border-radius: 3px;
  font-weight: 600;
  background: var(--green);
  color: #F7FAF2;
  border: 1px solid var(--green);
}}
.stButton button:hover, [data-testid="stFormSubmitButton"] button:hover {{
  background: var(--green-deep);
  border-color: var(--green-deep);
}}
:focus-visible {{ outline: 2px solid var(--blue) !important; outline-offset: 2px !important; }}

.st-key-logout button {{
  background: transparent !important;
  color: var(--ink-soft) !important;
  border: 1px solid var(--line) !important;
  font-weight: 500 !important;
  padding: .15rem .8rem !important;
}}
.st-key-logout button:hover {{
  background: var(--paper) !important;
  color: var(--ink) !important;
}}

[data-testid="stTextInput"] input {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-bottom: 2px solid var(--ink-soft);
  border-radius: 3px;
}}
[data-testid="stExpander"] {{
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 3px;
}}
[data-testid="stExpander"] summary {{ font-family: var(--serif); color: var(--ink); }}
[data-testid="stDataFrame"] {{ border: 1px solid var(--line); border-radius: 3px; }}
[data-testid="stAlertContainer"] {{
  background: var(--panel) !important;
  border: 1px solid var(--line) !important;
  border-left: 3px solid var(--blue) !important;
  border-radius: 3px !important;
  padding: .55rem .75rem !important;
  color: var(--ink) !important;
}}
[data-testid="stAlert"], [data-testid="stAlertContentInfo"] {{
  background: transparent !important;
  border: none !important;
  color: var(--ink) !important;
}}

/* 坐席台的三个页签 */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
  gap: 1.4rem;
  border-bottom: 1px solid var(--line);
}}
[data-testid="stTabs"] [data-baseweb="tab"] {{
  background: transparent;
  color: var(--ink-soft);
  font-family: var(--serif);
  padding: .3rem 0;
}}
[data-testid="stTabs"] [aria-selected="true"] {{ color: var(--green-deep); }}

/* 顶栏：一行身份 + 退出，不占版面 */
.who {{ color: var(--ink-soft); font-size: .82rem; }}
.who strong {{ color: var(--ink); }}

@media (prefers-reduced-motion: no-preference) {{
  .block-container {{ animation: settle .24s ease-out both; }}
  @keyframes settle {{
    from {{ opacity: 0; transform: translateY(5px); }}
    to {{ opacity: 1; transform: none; }}
  }}
}}
@media (prefers-reduced-motion: reduce) {{
  * {{ animation: none !important; transition: none !important; }}
}}
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def card_head(kicker: str, title: str, sub: str = "") -> None:
    sub_html = f'<p class="card-sub">{sub}</p>' if sub else ""
    st.markdown(
        f'<div class="card-kicker">{kicker}</div>'
        f'<div class="card-title">{title}</div>{sub_html}',
        unsafe_allow_html=True,
    )
