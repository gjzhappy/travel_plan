import pytest
from travel_plan.agents.requirement_agent import RequirementAgent
from travel_plan.errors import RequirementError
from travel_plan.models.requirement import Requirement

@pytest.mark.parametrize("text,check",[
 ("上海4天，2个成人1个孩子，必须去迪士尼",lambda r:r.days==4 and r.party.child==1 and "上海迪士尼" in r.must_visit),
 ("上海3天，住宿固定",lambda r:r.lodging_strategy=="fixed"),
 ("上海3天，住宿灵活，最多换一次",lambda r:r.lodging_strategy=="flexible" and r.max_hotel_changes==1),
 ("上海3天，喜欢科技、自然和夜景",lambda r:set(r.interests)>={"科技","自然","夜景"}),
])
def test_initial_parser(text,check): assert check(RequirementAgent().parse(text)[0])

def test_modification_scopes():
    agent=RequirementAgent();base=agent.parse("上海4天")[0]
    assert agent.parse("第二天晚饭改成火锅",base)[1]["scope"]=="MEAL"
    req,intent=agent.parse("第二天不要去博物馆",base);assert intent["scope"]=="DAY" and "博物馆" in req.rejected_categories
    assert agent.parse("第二天下午景点换掉",base)[1]["scope"]=="NODE"
    assert agent.parse("第一天满意，不要再改",base)[1]["lock_day"]==1

def test_budget_change_and_validation():
    base=RequirementAgent().parse("上海3天，预算5000")[0]
    assert RequirementAgent().parse("预算减少1000",base)[0].budget==4000
    with pytest.raises(RequirementError):Requirement(days=0)
    with pytest.raises(RequirementError):Requirement(start_date="bad")

