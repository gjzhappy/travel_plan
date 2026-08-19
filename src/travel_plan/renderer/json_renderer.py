import json
class JSONRenderer:
    def render(self,plan):return json.dumps(plan.to_dict(),ensure_ascii=False,indent=2)

