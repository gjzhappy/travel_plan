import argparse,json,logging
from pathlib import Path
from travel_plan.config import DEFAULT_CONFIG
from travel_plan.retrieval.map_client import MockMapClient
from travel_plan.retrieval.qdrant_repository import OfflineSemanticRepository
from travel_plan.agents.client import OpenCodeAgentClient
from travel_plan.retrieval.service import RetrievalService
from travel_plan.retrieval.sqlite_repository import SQLiteRepository
from travel_plan.retrieval.weather_client import MockWeatherClient
from travel_plan.workflow import TravelWorkflow

def build_workflow(root=Path("."),state_dir=None,real_agents=False):
    seed_dir=root/"data/seed"
    facts=SQLiteRepository(root/"data/travel.db",seed_dir=seed_dir,auto_initialize=True);docs=json.loads((seed_dir/"guides.json").read_text(encoding="utf-8"))
    vectors=OfflineSemanticRepository(docs);weather=MockWeatherClient();retrieval=RetrievalService(vectors,facts,weather,DEFAULT_CONFIG.qdrant_top_k)
    return TravelWorkflow(retrieval,facts,MockMapClient(),state_dir or root/DEFAULT_CONFIG.state_dir,agent_client=OpenCodeAgentClient() if real_agents else None)
def cli():
    p=argparse.ArgumentParser();p.add_argument("request");p.add_argument("--trip-id");p.add_argument("--json",action="store_true");p.add_argument("--state-dir");args=p.parse_args();logging.basicConfig(level=logging.INFO,format="%(message)s")
    workflow=build_workflow(state_dir=args.state_dir,real_agents=True);plan,state,markdown=workflow.execute(args.request,args.trip_id)
    if args.json:
        from travel_plan.renderer.json_renderer import JSONRenderer
        print(JSONRenderer().render(__import__("travel_plan.workflow",fromlist=["_plan_from_dict"])._plan_from_dict(plan)))
    else: print(markdown)
    print(f"\nplan_version={state.version}")
if __name__=="__main__":cli()
