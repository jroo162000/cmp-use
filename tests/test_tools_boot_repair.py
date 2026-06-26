from cmpuse.agent_core import Agent


def test_boot_repair_dry_run():
    goal = {"tool": "boot_repair", "args": {}}
    agent = Agent()
    res = agent.run(agent.plan(goal), force=False)
    assert res[0]["status"] == "dry-run"
