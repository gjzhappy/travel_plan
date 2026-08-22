from pathlib import Path

from travel_plan.web.presenter import present_plan


STATIC = Path(__file__).parents[2] / "src" / "travel_plan" / "web" / "static"


def test_home_has_family_demo_quick_entry():
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "AI 上海旅行规划助手" in html
    assert "体验上海亲子4日游" in html
    assert "data/demo" not in html


def test_results_hide_details_by_default_and_can_expand_them():
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert '<details class="explain-overview">' in html
    assert "为什么这样安排？" in html
    assert "更多规划细节" in html
    assert '<details class="explain-overview" open>' not in html


def test_modify_uses_existing_api_and_versions_show_change_story():
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "`/api/plans/${planId}/modify`" in javascript
    assert "原计划 v${current.version-1}" in javascript
    assert "你的调整" in javascript
    assert "重新规划 v${current.version}" in javascript


def test_overview_contains_only_existing_requirement_and_plan_facts():
    plan = {
        "days": [{"day": 1, "theme": "浦东探索", "nodes": []}],
        "hotels": [], "budget": {"total": 1680}, "hotel_decision": {},
    }
    requirement = {
        "city": "上海", "party": {"adult": 2, "child": 1},
        "transport": "public_transit", "lodging_strategy": "fixed",
    }

    overview = present_plan(plan, 1, requirement)["overview"]

    assert overview == {
        "title": "上海1日游", "party": "2 成人 + 1 儿童",
        "transport": "公共交通优先", "lodging": "少换酒店",
        "budget": 1680, "route_features": ["浦东探索"],
    }
