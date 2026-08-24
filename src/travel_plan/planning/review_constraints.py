"""Compile supported review findings into executable planner constraints."""

from copy import deepcopy

from travel_plan.planning.pace_policy import max_attractions_for


def compile_review_constraints(requirement, review):
    result = deepcopy(requirement)
    limit = max_attractions_for(result)
    affected_days = sorted({
        issue.day for issue in review.issues
        if issue.type == "too_tiring" and issue.scope == "DAY" and issue.day is not None
    })
    changes = []
    if limit is None:
        return result, affected_days, changes
    for day in affected_days:
        before = result.day_constraints.get(day, {}).get("max_attractions")
        after = limit if before is None else min(before, limit)
        result.day_constraints.setdefault(day, {})["max_attractions"] = after
        if before != after:
            changes.append({"day": day, "before": before, "after": after})
    return result, affected_days, changes
