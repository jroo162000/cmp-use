import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from layered_agent_full.shared import state as state_module
import json


def test_audit_records_event(tmp_path):
    state_module.DB_PATH = tmp_path / "audit.db"
    state_module.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    s = state_module.CommanderState()

    s.audit("test", {"foo": "bar"})

    cur = s.conn.cursor()
    cur.execute("SELECT action, details FROM audit")
    row = cur.fetchone()
    assert row[0] == "test"
    assert json.loads(row[1]) == {"foo": "bar"}
