from cmpuse.agent_core import Agent


def test_net_ops_denied_by_default():
    agent = Agent()
    goal = {"tool": "net_ops", "args": {"url": "https://example.com"}}
    res = agent.run(agent.plan(goal), force=True)
    assert res[0]["status"] == "denied"

