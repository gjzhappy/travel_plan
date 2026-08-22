from travel_plan.web.server import AgentRuntimeStatus


def _stage(status="RUNNING", actor="requirement-agent", stage="REQUIREMENT"):
    return {"stage": stage, "actor": actor, "status": status}


def test_agent_runtime_emits_started_heartbeats_warning_and_completed():
    now = [100.0]
    streamed = []
    runtime = AgentRuntimeStatus(streamed.append, clock=lambda: now[0], heartbeat_seconds=999)

    runtime.observe(_stage())
    assert streamed[-1]["event"]["event_type"] == "AGENT_STARTED"
    assert streamed[-1]["event"]["status"] == "running"

    now[0] = 135.9
    first = runtime.snapshot()
    assert first["elapsed_seconds"] == 35
    assert "warning" not in first

    now[0] = 165.2
    warning = runtime.snapshot()
    assert warning["elapsed_seconds"] == 65
    assert warning["warning"] == "Agent响应较慢，请稍候"

    now[0] = 180.8
    runtime.observe(_stage("COMPLETED"))
    completed = streamed[-1]["event"]
    assert completed["event_type"] == "AGENT_COMPLETED"
    assert completed["duration_seconds"] == 80
    runtime.close()


def test_timeout_failure_has_read_only_recovery_suggestion():
    now = [0.0]
    streamed = []
    runtime = AgentRuntimeStatus(streamed.append, clock=lambda: now[0], heartbeat_seconds=999)
    runtime.observe(_stage())
    now[0] = 120

    runtime.fail(TimeoutError("agent timed out"))

    failed = streamed[-1]["event"]
    assert failed["event_type"] == "AGENT_FAILED"
    assert failed["status"] == "failed"
    assert failed["error"] == "timeout"
    assert failed["message"] == "Agent执行超时"
    assert "OpenCode Runtime" in failed["suggestion"]
    assert "Deterministic Offline Agent" in failed["suggestion"]
    runtime.close()


def test_requirement_and_review_agents_share_the_same_display_protocol():
    streamed = []
    runtime = AgentRuntimeStatus(streamed.append, heartbeat_seconds=999)

    runtime.observe(_stage(actor="requirement-agent", stage="REQUIREMENT"))
    requirement_fields = set(streamed[-1]["event"])
    runtime.observe(_stage("COMPLETED", actor="requirement-agent", stage="REQUIREMENT"))
    runtime.observe(_stage(actor="review-agent", stage="REVIEW"))
    review_fields = set(streamed[-1]["event"])

    assert requirement_fields == review_fields
    assert streamed[-1]["event"]["agent_label"] == "Review Agent"
    runtime.close()
