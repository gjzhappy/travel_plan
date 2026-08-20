from pathlib import Path

from travel_plan.config import Config
from travel_plan.conversation.state_manager import StateManager,TripState
from travel_plan.models.requirement import Requirement
from travel_plan.models.trip import Budget,DayPlan,HotelSegment,Node,TripPlan
from travel_plan.validation.validator import HardValidator
from travel_plan.retrieval.database import initialize_database
from travel_plan.retrieval.sqlite_repository import SQLiteRepository

def test_luggage_chain_and_budget(tmp_path):
 nodes=[Node("hotel_checkout","A","08:00","08:10"),Node("hotel_checkin","B","20:00","20:10")]
 plan=TripPlan("x",[DayPlan(1,"2026-08-19","",nodes)],[HotelSegment(1,"A",1,1,100),HotelSegment(2,"B",2,2,100)],Budget(hotels=1000))
 codes={x.code for x in HardValidator(Config()).validate(plan,Requirement(include_meals=False,budget=100,lodging_strategy="flexible",max_hotel_changes=1))}
 assert {"luggage_chain","budget_exceeded"}<=codes
 nodes.insert(1,Node("luggage_drop","B","08:10","08:30"));assert "luggage_chain" not in {x.code for x in HardValidator(Config()).validate(plan,Requirement(include_meals=False,budget=2000,lodging_strategy="flexible",max_hotel_changes=1))}


def test_consecutive_nodes_do_not_overlap():
 nodes=[Node("attraction","A","09:00","10:00"),Node("attraction","B","10:00","11:00"),Node("attraction","C","11:00","12:00")]
 plan=TripPlan("x",[DayPlan(1,"2026-08-19","",nodes)],[],Budget())
 issues=HardValidator(Config()).validate(plan,Requirement(include_meals=False))
 assert "overlap" not in {issue.code for issue in issues}


def test_third_node_overlapping_second_is_detected():
 nodes=[Node("attraction","A","09:00","10:00"),Node("attraction","B","10:00","11:00"),Node("attraction","C","10:30","12:00")]
 plan=TripPlan("x",[DayPlan(1,"2026-08-19","",nodes)],[],Budget())
 issues=HardValidator(Config()).validate(plan,Requirement(include_meals=False))
 assert "overlap" in {issue.code for issue in issues}


def test_versions_readable(tmp_path):
 sm=StateManager(tmp_path);sm.save(TripState("t",1,{}));sm.save(TripState("t",2,{}));sm.save(TripState("t",3,{}))
 assert [sm.load("t",i).version for i in (1,2,3)]==[1,2,3]


def test_database_rebuilds_from_seeds_and_is_repeatable(tmp_path):
    database = tmp_path / "nested" / "travel.db"
    seeds = Path(__file__).resolve().parents[2] / "data/seed"
    initialize_database(database, seeds)
    first = SQLiteRepository(database)
    assert len(first.all_pois("上海")) == 30
    assert len(first.restaurants("上海")) == 16
    assert len(first.hotels("上海")) == 4
    initialize_database(database, seeds)
    assert len(SQLiteRepository(database).all_pois("上海")) == 30
