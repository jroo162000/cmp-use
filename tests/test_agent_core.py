import json
from cmpuse.agent_core import Agent


def test_plan_and_dry_run_exec():
    goal = {"tool": "json_ops", "args": {"operation": "validate", "data": "{}"}}
    agent = Agent()
    plan = agent.plan(goal)
    res = agent.run(plan, force=False)
    assert res[0]["status"] == "dry-run"


def test_force_exec_json_validate():
    goal = {"tool": "json_ops", "args": {"operation": "validate", "data": "{}"}}
    agent = Agent()
    plan = agent.plan(goal)
    res = agent.run(plan, force=True)
    assert res[0]["status"] == "ok"
