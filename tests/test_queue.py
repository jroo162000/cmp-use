import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from layered_agent_full.shared import state as state_module
from layered_agent_full.shared.protocol import FunctionCall


def test_enqueue_fetch_once(tmp_path):
    # use isolated database
    db_path = tmp_path / "tasks.db"
    state_module.DB_PATH = db_path
    state_module.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    s = state_module.CommanderState()
    fc = FunctionCall(name="dummy", arguments={"a": 1})
    s.enqueue("worker1", fc)

    tasks = s.fetch_tasks("worker1")
    assert len(tasks) == 1
    assert tasks[0]["function"]["name"] == "dummy"

    # second fetch should yield nothing since task marked as sent
    assert s.fetch_tasks("worker1") == []
