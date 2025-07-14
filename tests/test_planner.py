import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from layered_agent_full.commander import planning


def test_planner_plan(tmp_path):
    planning.DB_PATH = tmp_path / "tasks.db"
    planning.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    planner = planning.Planner()

    tid = planner.plan("First task. Second task.")

    cur = planner.conn.cursor()
    cur.execute("SELECT id, description, scheduled_at FROM tasks ORDER BY scheduled_at")
    rows = cur.fetchall()

    assert len(rows) == 2
    assert rows[0][1] == "First task"
    assert rows[1][1] == "Second task"
    assert tid == rows[0][0]
    assert rows[0][2] < rows[1][2]
