import re
from datetime import date
from travel_plan.models.requirement import Party, Requirement
from travel_plan.agents.client import load_schema

CN={"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
def _number(text): return int(text) if text.isdigit() else CN.get(text,1)

class RequirementAgent:
    """Offline deterministic adapter; OpenCode may replace interpretation with its agent JSON."""
    def parse(self,text:str,existing:Requirement|None=None)->tuple[Requirement,dict]:
        base=existing.to_dict() if existing else {}; base.pop("party",None)
        city="上海" if "上海" in text else (existing.city if existing else "上海")
        m=re.search(r"([一二三四五六七八九十\d]+)天",text);days=_number(m.group(1)) if m else (existing.days if existing else 3)
        adult=re.search(r"(\d+)\s*(?:位|个)?成人",text);child=re.search(r"(\d+)\s*(?:位|个)?(?:孩子|儿童)",text)
        party=Party(int(adult.group(1)) if adult else (existing.party.adult if existing else 1),int(child.group(1)) if child else (existing.party.child if existing else 0))
        interests=list(existing.interests) if existing else []
        for word in ("科技","自然","夜景","历史","艺术","亲子"):
            if word in text and word not in interests:interests.append(word)
        must=list(existing.must_visit) if existing else []
        if "必须去迪士尼" in text and "上海迪士尼" not in must:must.append("上海迪士尼")
        rejected=list(existing.rejected_pois) if existing else [];rejected_categories=list(existing.rejected_categories) if existing else []
        if "不要去博物馆" in text or "不要再推荐博物馆" in text:
            if "博物馆" not in rejected_categories:rejected_categories.append("博物馆")
        m=re.search(r"不要(?:去)?([\u4e00-\u9fa5]{3,12}(?:馆|园|塔|中心))",text)
        if m and m.group(1)!="博物馆" and m.group(1) not in rejected:rejected.append(m.group(1))
        foods=list(existing.food_preferences) if existing else []
        for food in ("本帮菜","火锅","素食","小笼包"):
            if food in text and food not in foods:foods.append(food)
        budget=existing.budget if existing else 5000
        bm=re.search(r"预算(?:改为|减少)?\s*(\d+)",text)
        if bm: budget=max(0,budget-int(bm.group(1))) if "减少" in text else int(bm.group(1))
        lodging="fixed" if "住宿固定" in text or "不换酒店" in text else ("flexible" if "住宿灵活" in text else (existing.lodging_strategy if existing else "fixed"))
        changes=existing.max_hotel_changes if existing else 0
        cm=re.search(r"最多换(?:酒店)?([一二三四五六七八九十\d]+)次",text)
        if cm:changes=_number(cm.group(1))
        pace="relaxed" if any(x in text for x in ("不要太赶","轻松","慢")) else ("intensive" if "紧凑" in text else (existing.pace if existing else "moderate"))
        scope="GLOBAL";day_no=None
        dm=re.search(r"第([一二三四五六七八九十\d]+)天",text)
        if dm: day_no=_number(dm.group(1));scope="MEAL" if any(x in text for x in ("晚餐","晚饭","午餐")) else ("NODE" if "换掉" in text or "替换" in text else "DAY")
        lock=day_no if day_no and any(x in text for x in ("满意","不要再改","锁定")) else None
        target_name=None
        nm=re.search(r"(?:把)?第[一二三四五六七八九十\d]+天(?:下午)?(?:的)?([\u4e00-\u9fa5]{2,15})(?:换掉|替换)",text)
        if nm: target_name=nm.group(1)
        meal="dinner" if "晚" in text else "lunch"
        req=Requirement(city,days,existing.start_date if existing else date.today().isoformat(),party,interests,pace,"public_transit" if "公共交通" in text or not existing else existing.transport,"low" if "少走路" in text else (existing.walking if existing else "medium"),must,rejected,rejected_categories,foods,True,lodging,changes,budget," ".join(interests+must+(["亲子"] if party.child else [])),True,scope,day_no,None,target_name,meal if scope=="MEAL" else None,foods if scope=="MEAL" else [])
        return req,{"scope":scope,"day":day_no,"meal":"dinner" if "晚" in text else "lunch","lock_day":lock}

class OpenCodeRequirementAgent:
    def __init__(self,client): self.client=client;self.schema=load_schema("requirement")
    def parse(self,text,existing=None,current_plan=None):
        raw=self.client.invoke("requirement-agent",{"user_text":text,"trip_state_requirement":existing.to_dict() if existing else None,"current_plan":current_plan},self.schema)
        req=Requirement.from_dict(raw)
        return req,{"scope":req.scope,"day":req.target_day,"meal":req.target_meal,"lock_day":None,"target_node_id":req.target_node_id,"target_poi_name":req.target_poi_name}
