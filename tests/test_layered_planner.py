from cmpuse.agent_core import Agent


def test_layered_planner_splits_steps():
    agent = Agent()
    goal = {"tool": "layered_planner", "args": {"goal": "Do A. Do B. Do C"}}
    res = agent.run(agent.plan(goal), force=True)
    steps = res[0]["steps"]
    assert steps == ["Do A", "Do B", "Do C"]
