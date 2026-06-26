from cmpuse.agent_core import Agent


def test_json_merge():
    agent = Agent()
    goal = {"tool": "json_ops", "args": {"operation": "merge", "a": {"x": 1}, "b": {"y": 2}}}
    res = agent.run(agent.plan(goal), force=True)
    assert res[0]["result"] == {"x": 1, "y": 2}
