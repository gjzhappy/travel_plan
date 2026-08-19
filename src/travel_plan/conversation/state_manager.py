import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class TripState:
    trip_id:str; version:int; requirements:dict[str,Any]; locked_items:list[str]=field(default_factory=list)
    rejected_items:list[str]=field(default_factory=list);rejected_categories:list[str]=field(default_factory=list);current_plan:dict[str,Any]=field(default_factory=dict)

class StateManager:
    def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
    def save(self,state:TripState):
        trip=self.root/state.trip_id;trip.mkdir(exist_ok=True)
        data=json.dumps(asdict(state),ensure_ascii=False,indent=2)
        (trip/f"version_{state.version}.json").write_text(data,encoding="utf-8");(trip/"current.json").write_text(data,encoding="utf-8")
    def load(self,trip_id,version=None):
        path=self.root/trip_id/(f"version_{version}.json" if version else "current.json")
        if not path.exists():return None
        return TripState(**json.loads(path.read_text(encoding="utf-8")))
    def next_version(self,trip_id):
        current=self.load(trip_id);return 1 if current is None else current.version+1

