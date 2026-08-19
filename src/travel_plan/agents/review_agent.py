from travel_plan.models.review import ReviewIssue, ReviewResult

class ReviewAgent:
    def review(self,req,plan,evidence=None):
        issues=[]
        for day in plan.days:
            attractions=[n for n in day.nodes if n.type=="attraction"]
            if (req.pace=="relaxed" and len(attractions)>3) or (req.party.child and len(attractions)>4): issues.append(ReviewIssue("DAY","too_tiring","景点数量对当前节奏偏多",day.day))
            cats=[n.metadata.get("category") for n in attractions]
            if len(cats)>=3 and len(set(cats))==1:issues.append(ReviewIssue("DAY","content_repetitive","同类内容连续重复",day.day))
        scheduled=" ".join(n.name+str(n.metadata.get("category","")) for d in plan.days for n in d.nodes)
        if req.interests and not any(i in scheduled for i in req.interests):issues.append(ReviewIssue("GLOBAL","preference_not_reflected","兴趣偏好未体现"))
        return ReviewResult(not issues,issues,[f"按{issue.scope}范围处理：{issue.message}" for issue in issues])
