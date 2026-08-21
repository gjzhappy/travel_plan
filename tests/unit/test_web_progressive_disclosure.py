from pathlib import Path


STATIC = Path(__file__).parents[2] / "src" / "travel_plan" / "web" / "static"


def test_explainability_uses_progressive_disclosure_without_a_mode_switch():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "为什么这样安排？" in html
    assert "更多规划细节" in html
    assert '<details class="explain-overview">' in html
    assert "explain-toggle" not in html
    assert "explain-toggle" not in javascript
    assert "explain-mode" not in javascript


def test_removed_mode_language_does_not_appear_in_the_interface():
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    for removed_term in ("评委模式", "技术模式", "普通模式", "高级解释层"):
        assert removed_term not in html
