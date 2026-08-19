from copy import deepcopy

class CodeRepair:
    """Conservative deterministic repairs; it never reports success while issues remain."""
    def repair(self,plan,issues,req,restaurants=None):
        fixed=deepcopy(plan)
        for issue in issues:
            day=next((d for d in fixed.days if d.day==issue.day),None)
            if not day:continue
            if issue.code in {"poi_closed_or_late","overlap"}:
                candidates=[n for n in day.nodes if n.type=="attraction" and n.name not in req.must_visit]
                if candidates: day.nodes.remove(min(candidates,key=lambda n:n.metadata.get("priority",0)))
            elif issue.code=="restaurant_closed" and restaurants:
                # replacement is delegated to MealPlanner by removing the invalid node
                day.nodes=[n for n in day.nodes if n.name!=issue.node]
            elif issue.code=="invalid_duration":
                node=next((n for n in day.nodes if n.name==issue.node),None)
                if node: node.end_time=node.start_time
        return fixed

