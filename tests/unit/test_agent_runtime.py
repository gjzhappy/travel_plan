from pathlib import Path
import pytest
from travel_plan.agents.client import FakeOpenCodeAgentClient
from travel_plan.agents.requirement_agent import OpenCodeRequirementAgent
from travel_plan.errors import AgentOutputValidationError
from travel_plan.main import build_workflow
from travel_plan.models.requirement import Requirement

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
