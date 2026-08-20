from pathlib import Path
import pytest
from travel_plan.agents.client import FakeOpenCodeAgentClient
from travel_plan.agents.requirement_agent import OpenCodeRequirementAgent, preserve_user_intent
from travel_plan.errors import AgentOutputValidationError, ValidationError
from travel_plan.main import build_workflow
from travel_plan.models.requirement import Party, Requirement

def requirement_json():
    value=Requirement(days=1,start_date="2026-08-19",include_meals=False).to_dict()
    return value

def test_workflow_explicitly_invokes_both_named_agents(tmp_path):
    fake=FakeOpenCodeAgentClient([requirement_json(),{"passed":True,"issues":[],"repair_instructions":[]}])
    workflow=build_workflow(Path.cwd(),tmp_path);workflow.requirements=OpenCodeRequirementAgent(fake)
    from travel_plan.agents.review_agent import OpenCodeReviewAgent
    workflow.reviewer=OpenCodeReviewAgent(fake)
    workflow.execute("上海一日游","agent_runtime")
    assert [call[0] for call in fake.calls]==["requirement-agent","review-agent"]

def test_invalid_requirement_agent_output_fails_closed():
    fake=FakeOpenCodeAgentClient([{"city":"上海"}])
    with pytest.raises(AgentOutputValidationError): OpenCodeRequirementAgent(fake).parse("上海")

def test_invalid_review_agent_output_fails_closed():
    from travel_plan.agents.review_agent import OpenCodeReviewAgent
    fake=FakeOpenCodeAgentClient([{"passed":"yes","issues":[],"repair_instructions":[]}])
    with pytest.raises(AgentOutputValidationError): fake.invoke("review-agent",{},OpenCodeReviewAgent(fake).schema)

def test_failed_review_returns_to_intent_agent_before_code_replan(tmp_path):
    initial=requirement_json()
    refined={**initial,"pace":"relaxed","scope":"DAY","target_day":1,
             "replacement_constraints":["too_tiring"]}
    feedback={"passed":False,"issues":[{"scope":"DAY","type":"too_tiring",
              "message":"too many stops","day":1}],"repair_instructions":["reduce load"]}
    fake=FakeOpenCodeAgentClient([initial,feedback,refined,
                                  {"passed":True,"issues":[],"repair_instructions":[]}])
    workflow=build_workflow(Path.cwd(),tmp_path)
    workflow.requirements=OpenCodeRequirementAgent(fake)
    from travel_plan.agents.review_agent import OpenCodeReviewAgent
    workflow.reviewer=OpenCodeReviewAgent(fake)
    _,state,_=workflow.execute("上海一日游","feedback_loop")
    assert [call[0] for call in fake.calls]==[
        "requirement-agent","review-agent","requirement-agent","review-agent"]
    refinement_payload=fake.calls[2][1]
    assert refinement_payload["task"]=="refine_intent_from_review"
    assert refinement_payload["review_feedback"]==feedback
    assert state.requirements["replacement_constraints"]==["too_tiring"]


def test_review_refinement_cannot_overwrite_original_user_intent():
    original=Requirement(
        city="上海",days=4,start_date="2026-08-19",party=Party(2,1),
        interests=["科技"],pace="intensive",must_visit=["上海迪士尼"],
        rejected_categories=["博物馆"],budget=8000,retrieval_query="科技",
    )
    # Construct through the schema-facing representation, as an agent response is.
    proposed=Requirement.from_dict({
        **original.to_dict(),"city":"北京","days":1,"party":{"adult":1,"child":0},
        "interests":[],"pace":"relaxed","must_visit":[],"rejected_categories":[],
        "budget":100,"scope":"DAY","target_day":2,
        "replacement_constraints":["too_tiring"],"retrieval_query":"科技 too_tiring",
    })
    preserved=preserve_user_intent(original,proposed)
    for field in ("city","days","party","interests","pace","must_visit",
                  "rejected_categories","budget"):
        assert getattr(preserved,field)==getattr(original,field)
    assert preserved.scope=="DAY" and preserved.target_day==2
    assert preserved.replacement_constraints==["too_tiring"]
    assert preserved.retrieval_query=="科技 too_tiring"


def test_final_validator_is_acceptance_gate_and_invalid_plan_is_not_saved(tmp_path):
    workflow=build_workflow(Path.cwd(),tmp_path)
    from travel_plan.validation.validator import ValidationIssue
    workflow.validator.validate=lambda plan,req: [ValidationIssue("forced","still invalid")]
    with pytest.raises(ValidationError,match="final validation gate"):
        workflow.execute("上海一日游","invalid_final")
    assert workflow.state.load("invalid_final") is None
