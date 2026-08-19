#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from travel_plan.main import build_workflow
request="上海4天，2位成人和1个孩子，喜欢科技、自然和夜景，节奏不要太赶；公共交通优先，少走路；午餐和晚餐都需要安排，想吃本帮菜和火锅；住宿灵活，最多换1次；有行李；必须去迪士尼。"
_,state,markdown=build_workflow(Path(__file__).resolve().parents[1]).execute(request,"trip_demo")
print(markdown);print(f"\nplan_version={state.version}")
