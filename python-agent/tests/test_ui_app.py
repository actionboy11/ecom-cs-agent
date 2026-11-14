"""S7-1/视觉：Streamlit 页面能加载（不依赖后端）。"""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from ui import theme

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "ui" / "app.py"


def test_login_page_renders_without_backend() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=15)

    assert not app.exception, app.exception
    html = " ".join(str(m.value) for m in app.markdown)
    assert "售后调度台" in html
    assert "把每一单售后" in html


def test_theme_has_waybill_and_accessibility_rules() -> None:
    assert theme.TOKENS["green"] in theme.CSS
    assert ".waybill" in theme.CSS
    assert "prefers-reduced-motion" in theme.CSS
    assert ":focus-visible" in theme.CSS
