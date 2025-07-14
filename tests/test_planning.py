import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from layered_agent_full.commander import planning


def test_task_insertion_and_retrieval(tmp_path):
    planning.DB_PATH = tmp_path / "tasks.db"
    planning.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    planner = planning.Planner()

    tid = planner.plan("Single task.")

    due = planner.fetch_due()
    assert len(due) == 1
    row = due[0]
    assert row[0] == tid
    assert row[2] == "Single task"

    planner.mark_done(tid)
    assert planner.fetch_due() == []
