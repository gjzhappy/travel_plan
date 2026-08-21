"""Explicit, schema-checked boundary to the two OpenCode agents."""
from __future__ import annotations
import json, subprocess
from pathlib import Path
from typing import Any, Protocol
from travel_plan.errors import AgentOutputValidationError

ROOT=Path(__file__).resolve().parents[3]

class AgentClient(Protocol):
    def invoke(self,agent_name:str,payload:dict[str,Any],schema:dict[str,Any])->dict[str,Any]: ...

def load_schema(name:str)->dict[str,Any]:
    return json.loads((ROOT/"schemas"/f"{name}.schema.json").read_text(encoding="utf-8"))

def validate_agent_output(value:object,schema:dict[str,Any],agent_name:str)->dict[str,Any]:
    try:
        try:
            from jsonschema import Draft202012Validator
            errors=sorted(Draft202012Validator(schema,format_checker=None).iter_errors(value),key=lambda e:list(e.path))
            if errors: raise ValueError("; ".join(f"{'.'.join(map(str,e.path)) or '$'}: {e.message}" for e in errors))
        except ImportError:
            def check(v,s,path="$"):
                expected=s.get("type")
                types=expected if isinstance(expected,list) else [expected]
                mapping={"object":dict,"array":list,"string":str,"integer":int,"number":(int,float),"boolean":bool,"null":type(None)}
                if expected and not any(isinstance(v,mapping[t]) and not (t in {"integer","number"} and isinstance(v,bool)) for t in types): raise ValueError(f"{path}: wrong type")
                if "enum" in s and v not in s["enum"]: raise ValueError(f"{path}: value outside enum")
                if isinstance(v,dict):
                    missing=[k for k in s.get("required",[]) if k not in v]
                    if missing: raise ValueError(f"{path}: missing {missing}")
                    for k,x in v.items():
                        if k in s.get("properties",{}):check(x,s["properties"][k],f"{path}.{k}")
                if isinstance(v,list) and "items" in s:
                    for i,x in enumerate(v):check(x,s["items"],f"{path}[{i}]")
            check(value,schema)
    except (TypeError,ValueError) as exc:
        raise AgentOutputValidationError(f"{agent_name}: {exc}") from exc
    if not isinstance(value,dict): raise AgentOutputValidationError(f"{agent_name}: output must be an object")
    return value

class OpenCodeAgentClient:
    """Invoke a specific agent; never delegates agent selection to another model."""
    def __init__(self,executable:str="opencode",timeout:int=120): self.executable=executable;self.timeout=timeout
    def invoke(self,agent_name,payload,schema):
        prompt=json.dumps({"payload":payload,"output_schema":schema},ensure_ascii=False)
        try:
            proc=subprocess.run([self.executable,"run","--agent",agent_name,prompt],text=True,capture_output=True,timeout=self.timeout,check=True)
            text=proc.stdout.strip(); start=text.find("{"); end=text.rfind("}")
            if start<0 or end<start: raise ValueError("no JSON object in agent output")
            value=json.loads(text[start:end+1])
        except (OSError,subprocess.SubprocessError,ValueError,json.JSONDecodeError) as exc:
            raise AgentOutputValidationError(f"{agent_name} invocation failed: {exc}") from exc
        return validate_agent_output(value,schema,agent_name)

class DeterministicAgentClient:
    """Offline implementation of the same named-agent invocation boundary."""
    def __init__(self, reference_date):
        self.reference_date=reference_date; self.calls=[]
    def invoke(self,agent_name,payload,schema):
        self.calls.append((agent_name,payload))
        if agent_name=="requirement-agent":
            from datetime import date
            from travel_plan.agents.requirement_agent import RequirementAgent
            from travel_plan.models.requirement import Requirement
            agent=RequirementAgent(date.fromisoformat(self.reference_date))
            existing=Requirement.from_dict(payload["trip_state_requirement"]) if payload.get("trip_state_requirement") else None
            if payload.get("task")=="refine_intent_from_review":
                from travel_plan.models.review import ReviewIssue, ReviewResult
                raw=payload["review_feedback"]
                review=ReviewResult(raw["passed"],[ReviewIssue(**x) for x in raw["issues"]],raw["repair_instructions"])
                value=agent.refine(existing,review,payload.get("current_plan")).to_dict()
            else:
                value=agent.parse(payload["user_text"],existing)[0].to_dict()
        elif agent_name=="review-agent":
            from travel_plan.agents.review_agent import ReviewAgent
            from travel_plan.models.requirement import Requirement
            from travel_plan.workflow import _plan_from_dict
            value=ReviewAgent().review(Requirement.from_dict(payload["requirement"]),_plan_from_dict(payload["trip_plan"]),payload.get("evidence")).to_dict()
        else: raise AgentOutputValidationError(f"unknown agent: {agent_name}")
        return validate_agent_output(value,schema,agent_name)

# Provider-facing name retained alongside the implementation-oriented name.
MockAgentClient = DeterministicAgentClient

class FakeOpenCodeAgentClient:
    def __init__(self,responses): self.responses=list(responses);self.calls=[]
    def invoke(self,agent_name,payload,schema):
        self.calls.append((agent_name,payload,schema))
        if not self.responses: raise AssertionError("no fake agent response")
        return validate_agent_output(self.responses.pop(0),schema,agent_name)
