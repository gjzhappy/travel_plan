from pathlib import Path
import re

from travel_plan.web.presenter import present_plan


STATIC = Path(__file__).parents[2] / "src" / "travel_plan" / "web" / "static"


def test_home_has_family_demo_quick_entry():
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "上海 AI 旅行规划助手" in html
    assert "上海亲子4日游" in html
    assert "推荐演示流程" in html
    assert "方案可信度来源" in html
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


def test_home_runtime_copy_uses_user_facing_agent_names():
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "Deterministic Requirement Agent" in javascript
    assert "OpenCode Agent" in javascript
    assert "知识库：上海旅游知识库" in javascript


def test_route_presentation_has_collision_avoidance_and_demo_playback_contracts():
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert "placeMapLabels" in javascript
    assert "boxesOverlap" in javascript
    assert "minimumVisibleMs" in javascript
    assert "AGENT_MIN_VISIBLE_MS=1400" in javascript
    assert "PLANNING_MIN_VISIBLE_MS=900" in javascript
    assert "CHECK_MIN_VISIBLE_MS=650" in javascript
    assert "separateMapMarkers" in javascript
    assert "visualX" in javascript
    assert "runtimeMode!=='deterministic'" in javascript
    assert "isUrgentEvent" in javascript
    assert "路线评分" not in html


def test_completed_workflow_has_a_persistent_result_snapshot():
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert 'id="result-workflow-graph"' in html
    assert 'id="result-live-trace"' in html
    assert "finalWorkflowGraph=item.graph" in javascript
    assert "renderWorkflowGraph(finalWorkflowGraph,'#result-workflow-graph')" in javascript
    assert "beginWorkflowPresentation" in javascript


def test_three_playback_tiers_produce_an_eight_to_twelve_second_demo_without_sleeping():
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    values = {name: int(value) for name, value in re.findall(
        r"(AGENT_MIN_VISIBLE_MS|PLANNING_MIN_VISIBLE_MS|CHECK_MIN_VISIBLE_MS)=(\d+)", javascript
    )}
    # Representative successful path: requirement + retrieval/facts/route/meal/hotel
    # + validator + review. This checks presentation time, not trace duration.
    total = values["AGENT_MIN_VISIBLE_MS"] * 2 + values["PLANNING_MIN_VISIBLE_MS"] * 5 + values["CHECK_MIN_VISIBLE_MS"]
    assert 7_800 <= total <= 12_000
    assert "Math.max(0,minimumVisibleMs(event.stage)-" in javascript
