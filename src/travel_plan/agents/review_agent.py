from travel_plan.models.review import ReviewIssue, ReviewResult
from travel_plan.agents.client import load_schema
from travel_plan.planning.pace_policy import max_attractions_for

class ReviewAgent:
    def review(self,req,plan,evidence=None):
        issues=[]
        for day in plan.days:
            attractions=[n for n in day.nodes if n.type=="attraction"]
            limit=max_attractions_for(req)
            if limit is not None and len(attractions)>limit: issues.append(ReviewIssue("DAY","too_tiring","景点数量对当前节奏偏多",day.day))
            cats=[n.metadata.get("category") for n in attractions]
            if len(cats)>=3 and len(set(cats))==1:issues.append(ReviewIssue("DAY","content_repetitive","同类内容连续重复",day.day))
        scheduled=" ".join(n.name+str(n.metadata.get("category","")) for d in plan.days for n in d.nodes)
        if req.interests and not any(i in scheduled for i in req.interests):issues.append(ReviewIssue("GLOBAL","preference_not_reflected","兴趣偏好未体现"))
        return ReviewResult(not issues,issues,[f"按{issue.scope}范围处理：{issue.message}" for issue in issues])

class OpenCodeReviewAgent:
    def __init__(self,client): self.client=client;self.schema=load_schema("review")
    def review(self,req,plan,evidence=None):
        raw=self.client.invoke("review-agent",{"requirement":req.to_dict(),"trip_plan":plan.to_dict(),"evidence":evidence or []},self.schema)
        return ReviewResult(raw["passed"],[ReviewIssue(**x) for x in raw["issues"]],raw["repair_instructions"])
