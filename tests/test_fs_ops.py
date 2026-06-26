import os
from pathlib import Path
from cmpuse.agent_core import Agent


def test_fs_write_is_dryrun(tmp_path, monkeypatch):
    # whitelist the temp directory
    monkeypatch.setenv("CMPUSE_PATH_WHITELIST", str(tmp_path))
    agent = Agent()
    target = tmp_path / "hello.txt"
    goal = {"tool": "fs_ops", "args": {"operation": "write", "path": str(target), "content": "hi"}}
    res = agent.run(agent.plan(goal), force=False)
    assert res[0]["status"] == "dry-run"


def test_fs_read_denied_outside_whitelist(tmp_path, monkeypatch):
    # whitelist a different directory
    allowed = tmp_path / "allowed"; allowed.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    f = outside / "x.txt"; f.write_text("x")
    monkeypatch.setenv("CMPUSE_PATH_WHITELIST", str(allowed))
    agent = Agent()
    goal = {"tool": "fs_ops", "args": {"operation": "read", "path": str(f)}}
    res = agent.run(agent.plan(goal), force=True)
    assert res[0]["status"] == "denied"

