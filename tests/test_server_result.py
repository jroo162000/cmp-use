import sys
from pathlib import Path
import json
import importlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from layered_agent_full.shared import state as state_module


def test_post_result_without_secrets(tmp_path, monkeypatch):
    # Redirect HOME so secrets.toml does not exist
    monkeypatch.setenv('HOME', str(tmp_path))

    # Use isolated database
    state_module.DB_PATH = tmp_path / 'tasks.db'
    state_module.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Provide OpenAI key so server import succeeds
    monkeypatch.setenv('OPENAI_API_KEY', 'dummy')

    server = importlib.reload(importlib.import_module('layered_agent_full.commander.server'))

    tid = 't123'
    payload = {'x': 1}
    body = {'payload': json.dumps(payload)}

    resp = server.post_result(tid, body=body, authorization=server.state.bearer_token)
    assert resp == {'status': 'ok'}

    msg = server.state.history[-1]
    data = json.loads(msg.content)
    assert data['task_id'] == tid
    assert data['result'] == payload
