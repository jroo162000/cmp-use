from cmpuse.agent_core import Agent


def test_scenario_boot_repair_dryrun():
    agent = Agent()
    goal = {
        "steps": [
            {"tool": "sys_ops"},
            {"tool": "boot_repair"},
        ]
    }
    plan = agent.plan(goal)
    res = agent.run(plan, force=False)
    assert len(res) == 2
    assert res[1]["status"] == "dry-run"
