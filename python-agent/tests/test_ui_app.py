"""S7-1：Streamlit 页面能加载（不依赖后端）。"""

from __future__ import annotations

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "ui" / "app.py"


def test_login_page_renders_without_backend() -> None:
    if str(ROOT / "ui") not in sys.path:
        sys.path.insert(0, str(ROOT / "ui"))

    app = AppTest.from_file(str(APP)).run(timeout=15)

    assert not app.exception, app.exception
    assert app.title[0].value == "电商售后客服工作台"
