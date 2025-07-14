"""Task Planning Module
Breaks high-level goals into scheduled tasks stored in a SQLite DB."""

import sqlite3
import uuid
from datetime import datetime, timedelta

DB_PATH = "./commander/tasks.db"


class Planner:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self._init_tables()

    def _init_tables(self):
        c = self.conn.cursor()
        c.execute(
            """
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            goal TEXT,
            description TEXT,
            status TEXT,
            scheduled_at TEXT
        )"""
        )
        self.conn.commit()

    def plan(self, goal: str) -> str:
        """Generate subtasks for a goal and schedule them 1 minute apart."""
        steps = [s.strip() for s in goal.split('.') if s.strip()]
        c = self.conn.cursor()
        ids = []
        now = datetime.utcnow()
        for i, step in enumerate(steps):
            tid = str(uuid.uuid4())
            when = now + timedelta(minutes=i)
            c.execute(
                "INSERT INTO tasks (id, goal, description, status, scheduled_at) VALUES (?,?,?,?,?)",
                (tid, goal, step, 'pending', when.isoformat()),
            )
            ids.append(tid)
        self.conn.commit()
        return ids[0] if ids else ''

    def fetch_due(self):
        c = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        c.execute(
            "SELECT id, goal, description, status, scheduled_at FROM tasks WHERE scheduled_at <= ? AND status='pending'",
            (now,),
        )
        return c.fetchall()

    def mark_done(self, task_id: str):
        c = self.conn.cursor()
        c.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
        self.conn.commit()
