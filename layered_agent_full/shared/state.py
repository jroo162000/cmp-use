from __future__ import annotations
import sqlite3
import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from layered_agent_full.shared.protocol import ChatMessage, make_skill_schema

# Use a path relative to this file so the DB is found regardless of CWD.
# The commander/planning module stores tasks in the same location.
DB_PATH = Path(__file__).resolve().parent.parent / "commander" / "tasks.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class CommanderState:
    def __init__(self):
        self.history: List[ChatMessage] = []
        self.workers: Dict[str, Dict[str, Any]] = {}
        self.skills: Dict[str, Dict[str, Any]] = {}
        self.bearer_token: str = secrets.token_hex(16)
        self.function_schema: List[Dict[str, Any]] = []
        self._memory_queue: Dict[str, List[Dict[str, Any]]] = {}
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        c = self.conn.cursor()
        c.execute(
            """
        CREATE TABLE IF NOT EXISTS audit (
            ts TEXT,
            action TEXT,
            details TEXT
        )"""
        )
        c.execute(
            """
        CREATE TABLE IF NOT EXISTS queue (
            id TEXT PRIMARY KEY,
            worker_id TEXT,
            status TEXT,
            payload TEXT
        )"""
        )
        self.conn.commit()

    def _audit(self, action: str, details: Dict[str, Any]):
        self.conn.execute(
            "INSERT INTO audit VALUES (?,?,?)",
            (datetime.utcnow().isoformat(), action, json.dumps(details)),
        )
        self.conn.commit()

    def register_worker(self, wid: str, info: Dict[str, Any]):
        self.workers[wid] = info
        for s in info.get("skills", []):
            self.skills[s["name"]] = s
        self.function_schema = make_skill_schema(self.skills)
        self._audit("register_worker", {"worker_id": wid})

    def get_worker_with_skill(self, name: str) -> Any:
        for wid, info in self.workers.items():
            if any(s['name'] == name for s in info.get('skills', [])):
                return wid
        return None

    def enqueue(self, worker_id: str, func_call: Any) -> str:
        task_id = secrets.token_hex(8)
        self._audit(
            'enqueue',
            {
                'task_id': task_id,
                'worker_id': worker_id,
                'function': getattr(func_call, 'name', ''),
                'arguments': getattr(func_call, 'arguments', {}),
            },
        )
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO queue (id, worker_id, status, payload) VALUES (?,?,?,?)",
            (
                task_id,
                worker_id,
                "pending",
                json.dumps({
                    "name": getattr(func_call, "name", ""),
                    "arguments": getattr(func_call, "arguments", {})
                }),
            ),
        )
        self.conn.commit()
        # also store in memory for quick retrieval
        task_obj = {
            "id": task_id,
            "function": {
                "name": getattr(func_call, "name", ""),
                "arguments": getattr(func_call, "arguments", {})
            }
        }
        self._memory_queue.setdefault(worker_id, []).append(task_obj)
        return task_id

    def fetch_tasks(self, worker_id: str) -> List[Dict[str, Any]]:
        tasks = self._memory_queue.pop(worker_id, [])
        mem_ids = [t["id"] for t in tasks]

        if mem_ids:
            placeholders = ",".join("?" for _ in mem_ids)
            c = self.conn.cursor()
            c.execute(
                f"UPDATE queue SET status='sent' WHERE id IN ({placeholders})",
                mem_ids,
            )
            self.conn.commit()

        c = self.conn.cursor()
        c.execute(
            "SELECT id, payload FROM queue WHERE worker_id=? AND status='pending'",
            (worker_id,),
        )
        rows = c.fetchall()
        db_ids = []
        for tid, payload in rows:
            db_ids.append(tid)
            tasks.append({"id": tid, "function": json.loads(payload)})
        if db_ids:
            placeholders = ",".join("?" for _ in db_ids)
            c.execute(
                f"UPDATE queue SET status='sent' WHERE id IN ({placeholders})",
                db_ids,
            )
            self.conn.commit()

        return tasks

    def complete(self, task_id: str, result: Any):
        self._audit('complete', {'task_id': task_id, 'result': result})
        self.history.append(
            ChatMessage(role='function', content=json.dumps({'task_id': task_id, 'result': result}))
        )
        self.history = self.history[-20:]

    def snapshot(self) -> Dict[str, Any]:
        return {
            'workers': list(self.workers.values()),
            'skills': list(self.skills.keys()),
            'bearer_token': self.bearer_token,
            'layer': 'L-3',
        }


# Test cases for planning and shared modules
if __name__ == '__main__':
    print('Testing shared.protocol.make_skill_schema...')
    from layered_agent_full.shared.protocol import make_skill_schema, ChatMessage

    schema = make_skill_schema([{'name': 'foo', 'description': 'desc', 'parameters': {}}])
    print('Schema:', schema)
    msg = ChatMessage(role='user', content='hello')
    print('ChatMessage:', msg)

    print('\nTesting Planner...')
    from layered_agent_full.commander.planning import Planner

    planner = Planner()
    tid = planner.plan('Step one. Step two.')
    print('Generated task id:', tid)
    due = planner.fetch_due()
    print('Due tasks:', due)
