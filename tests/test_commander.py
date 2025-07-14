import sys
from pathlib import Path
import importlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from layered_agent_full.shared.protocol import FunctionCall
from layered_agent_full.shared import state as state_module


def test_worker_registration_and_queue(tmp_path, monkeypatch):
    # isolate state DB
    state_module.DB_PATH = tmp_path / "tasks.db"
    state_module.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

    server = importlib.reload(importlib.import_module("layered_agent_full.commander.server"))
    client = TestClient(server.app)

    payload = {"token": server.state.bearer_token, "worker_id": "w1", "skills": []}
    resp = client.post("/register", json=payload)
    assert resp.status_code == 200
    assert resp.json()["worker_id"] == "w1"
    assert "w1" in server.state.workers

    server.state.enqueue("w1", FunctionCall(name="dummy", arguments={}))

    resp = client.get(f"/task/w1", headers={"Authorization": server.state.bearer_token})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["function"]["name"] == "dummy"
