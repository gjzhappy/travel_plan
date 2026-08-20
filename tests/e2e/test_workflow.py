import json
from pathlib import Path
from travel_plan.main import build_workflow

REQUEST="上海4天，2位成人和1个孩子，预算10000，喜欢科技、自然和夜景，节奏不要太赶；公共交通优先，少走路；午餐和晚餐都需要安排，想吃本帮菜和火锅；住宿灵活，最多换1次；有行李。"
def test_first_plan_meal_day_lock_and_versions(tmp_path):
 wf=build_workflow(Path.cwd(),tmp_path);plan,s1,md=wf.execute(REQUEST,"trip_e2e")
 assert s1.version==1 and "上海科技馆" in md and len(plan["days"])==4 and plan["review_count"]>=1
 day1=json.dumps(plan["days"][0],sort_keys=True,ensure_ascii=False)
 p2,s2,_=wf.execute("第二天晚饭改成火锅。","trip_e2e");assert s2.version==2
 assert json.dumps(p2["days"][0],sort_keys=True,ensure_ascii=False)==day1
 _,s3,_=wf.execute("第二天不要去博物馆。","trip_e2e");assert s3.version==3 and "博物馆" in s3.rejected_categories
 before=json.dumps(s3.current_plan["days"][0],sort_keys=True,ensure_ascii=False)
 _,s4,_=wf.execute("第一天满意，不要再改。","trip_e2e");assert "DAY:1" in s4.locked_items
 p5,s5,_=wf.execute("第三天晚饭改成火锅。","trip_e2e");assert json.dumps(p5["days"][0],sort_keys=True,ensure_ascii=False)==before and s5.version==5
