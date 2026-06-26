import time
from cmpuse.agent_core import Agent, Plan, Step
from cmpuse.tool_registry import register, Tool, _REGISTRY


def test_retries_succeeds_on_second_attempt(monkeypatch):
    calls = {"n": 0}

    def plan(args):
        return {"ok": True}

    def run(args, dry_run):
        calls["n"] += 1
        if calls["n"] < 2:
            return {"status": "error", "message": "transient"}
        return {"status": "ok", "value": 42}

    t = Tool(name="flaky", summary="", plan=plan, run=run)
    register(t)
    try:
        agent = Agent()
        plan_obj = Plan(steps=[Step(tool="flaky", args={})])
        res = agent.run(plan_obj, force=True, retries=2)
        assert res[0]["status"] == "ok"
        assert calls["n"] == 2
    finally:
        _REGISTRY.pop("flaky", None)


def test_timeout_triggers(monkeypatch):
    def plan(args):
        return {"ok": True}

    def run(args, dry_run):
        time.sleep(1.0)
        return {"status": "ok"}

    t = Tool(name="slow", summary="", plan=plan, run=run)
    register(t)
    try:
        agent = Agent()
        plan_obj = Plan(steps=[Step(tool="slow", args={})])
        res = agent.run(plan_obj, force=True, retries=0, timeout_sec=0.01)
        assert res[0]["status"] == "timeout"
    finally:
        _REGISTRY.pop("slow", None)

