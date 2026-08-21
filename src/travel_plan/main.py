import argparse,json,logging
from pathlib import Path
from travel_plan.config import DEFAULT_CONFIG
from travel_plan.retrieval.qdrant_repository import OfflineSemanticRepository
from travel_plan.providers import ProviderFactory
from travel_plan.retrieval.service import RetrievalService
from travel_plan.retrieval.sqlite_repository import SQLiteRepository
from travel_plan.workflow import TravelWorkflow

def build_workflow(root=Path("."),state_dir=None,config=DEFAULT_CONFIG):
    seed_dir=root/"data/seed"
    facts=SQLiteRepository(root/"data/travel.db",seed_dir=seed_dir,auto_initialize=True)
    source=seed_dir.resolve().parent/"source/shanghai_pois.json"
    pois=json.loads(source.read_text(encoding="utf-8"))
    docs=[{"poi_id":p["poi_id"],"city":"上海","semantic_description":" ".join(p["tags"]),"text":p["description"]} for p in pois]
    providers=ProviderFactory.create(config)
    vectors=OfflineSemanticRepository(docs);retrieval=RetrievalService(vectors,facts,providers.weather,config.qdrant_top_k)
    return TravelWorkflow(retrieval,facts,providers.map,state_dir or root/config.state_dir,config,providers.agent)
def cli():
    p=argparse.ArgumentParser();p.add_argument("request");p.add_argument("--trip-id");p.add_argument("--json",action="store_true");p.add_argument("--state-dir");args=p.parse_args();logging.basicConfig(level=logging.INFO,format="%(message)s")
    workflow=build_workflow(state_dir=args.state_dir);plan,state,markdown=workflow.execute(args.request,args.trip_id)
    if args.json:
        from travel_plan.renderer.json_renderer import JSONRenderer
        print(JSONRenderer().render(__import__("travel_plan.workflow",fromlist=["_plan_from_dict"])._plan_from_dict(plan)))
    else: print(markdown)
    print(f"\nplan_version={state.version}")
if __name__=="__main__":cli()
