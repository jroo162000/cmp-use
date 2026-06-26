"""
Proactive Assistance - Background monitoring, scheduled tasks, autonomous suggestions
"""

import schedule
import threading
import time
from .._lazyimport import lazy_module
psutil = lazy_module("psutil")   # deferred to first use
from datetime import datetime
from typing import Any, Dict, Callable
from ..tool_registry import Tool, register

class ProactiveAssistant:
    def __init__(self):
        self.running = False
        self.monitor_thread = None
        self.scheduled_tasks = []
        self.monitors = []
        self.suggestions = []

    def start_monitoring(self):
        """Start background monitoring thread"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()

    def stop_monitoring(self):
        """Stop background monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)

    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.running:
            # Run scheduled tasks
            schedule.run_pending()

            # Check system health
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Generate proactive suggestions
            if cpu_usage > 90:
                self.suggestions.append({
                    "type": "performance",
                    "message": "CPU usage is very high ({}%). Consider closing some applications.".format(cpu_usage),
                    "severity": "high",
                    "timestamp": datetime.now().isoformat()
                })

            if memory.percent > 90:
                self.suggestions.append({
                    "type": "performance",
                    "message": "Memory usage is critical ({}%). You may want to restart some applications.".format(memory.percent),
                    "severity": "high",
                    "timestamp": datetime.now().isoformat()
                })

            if disk.percent > 90:
                self.suggestions.append({
                    "type": "storage",
                    "message": "Disk space is running low ({}% used). Consider freeing up space.".format(disk.percent),
                    "severity": "medium",
                    "timestamp": datetime.now().isoformat()
                })

            # Limit suggestion history
            if len(self.suggestions) > 100:
                self.suggestions = self.suggestions[-50:]

            time.sleep(30)  # Check every 30 seconds

    def schedule_task(self, task_type, schedule_str, task_data):
        """Schedule a task using schedule library"""
        task_id = len(self.scheduled_tasks) + 1

        task = {
            "id": task_id,
            "type": task_type,
            "schedule": schedule_str,
            "data": task_data,
            "created_at": datetime.now().isoformat()
        }

        # Parse schedule string and add to scheduler
        # Examples: "every 1 hour", "every day at 10:00", "every monday"
        if "every" in schedule_str:
            parts = schedule_str.replace("every ", "").split()
            if "hour" in schedule_str:
                interval = int(parts[0]) if parts[0].isdigit() else 1
                schedule.every(interval).hours.do(lambda: self._execute_scheduled_task(task))
            elif "minute" in schedule_str:
                interval = int(parts[0]) if parts[0].isdigit() else 1
                schedule.every(interval).minutes.do(lambda: self._execute_scheduled_task(task))
            elif "day" in schedule_str:
                if "at" in schedule_str:
                    time_str = schedule_str.split("at ")[1]
                    schedule.every().day.at(time_str).do(lambda: self._execute_scheduled_task(task))
                else:
                    schedule.every().day.do(lambda: self._execute_scheduled_task(task))
            elif any(day in schedule_str.lower() for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
                day = next(d for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] if d in schedule_str.lower())
                getattr(schedule.every(), day).do(lambda: self._execute_scheduled_task(task))

        self.scheduled_tasks.append(task)
        return task

    def _execute_scheduled_task(self, task):
        """Execute a scheduled task"""
        print(f"Executing scheduled task: {task['type']} - {task['data']}")
        # Task execution would trigger appropriate AVA actions
        # This is a placeholder - actual execution would call AVA's tool system

proactive_assistant = ProactiveAssistant()

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "status")

    if action == "start":
        return {"preview": "Start proactive monitoring", "args": args}
    elif action == "stop":
        return {"preview": "Stop proactive monitoring", "args": args}
    elif action == "schedule_task":
        return {"preview": f"Schedule task: {args.get('task_type')}", "args": args}
    elif action == "get_suggestions":
        return {"preview": "Get proactive suggestions", "args": args}
    elif action == "list_tasks":
        return {"preview": "List scheduled tasks", "args": args}
    else:
        return {"preview": f"Proactive action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform proactive operation", "plan": _plan(args)}

    action = args.get("action", "status")

    try:
        if action == "start":
            proactive_assistant.start_monitoring()
            return {"status": "ok", "message": "Proactive monitoring started"}

        elif action == "stop":
            proactive_assistant.stop_monitoring()
            return {"status": "ok", "message": "Proactive monitoring stopped"}

        elif action == "status":
            return {
                "status": "ok",
                "running": proactive_assistant.running,
                "scheduled_tasks": len(proactive_assistant.scheduled_tasks),
                "pending_suggestions": len(proactive_assistant.suggestions)
            }

        elif action == "schedule_task":
            task_type = args.get("task_type")
            schedule_str = args.get("schedule")
            task_data = args.get("data", {})

            if not task_type or not schedule_str:
                return {"status": "error", "message": "task_type and schedule required"}

            task = proactive_assistant.schedule_task(task_type, schedule_str, task_data)
            return {"status": "ok", "message": "Task scheduled", "task": task}

        elif action == "list_tasks":
            return {
                "status": "ok",
                "tasks": proactive_assistant.scheduled_tasks,
                "count": len(proactive_assistant.scheduled_tasks)
            }

        elif action == "cancel_task":
            task_id = args.get("task_id")
            original_count = len(proactive_assistant.scheduled_tasks)
            proactive_assistant.scheduled_tasks = [t for t in proactive_assistant.scheduled_tasks if t['id'] != task_id]

            if len(proactive_assistant.scheduled_tasks) < original_count:
                return {"status": "ok", "message": f"Task {task_id} cancelled"}
            else:
                return {"status": "error", "message": f"Task {task_id} not found"}

        elif action == "get_suggestions":
            limit = args.get("limit", 10)
            suggestions = proactive_assistant.suggestions[-limit:]
            return {
                "status": "ok",
                "suggestions": suggestions,
                "count": len(suggestions)
            }

        elif action == "clear_suggestions":
            proactive_assistant.suggestions = []
            return {"status": "ok", "message": "Suggestions cleared"}

        elif action == "system_health":
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            health = {
                "cpu_usage": cpu_usage,
                "memory_usage": memory.percent,
                "disk_usage": disk.percent,
                "status": "healthy"
            }

            if cpu_usage > 90 or memory.percent > 90:
                health["status"] = "critical"
            elif cpu_usage > 75 or memory.percent > 75:
                health["status"] = "warning"

            return {"status": "ok", "health": health}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Proactive ops error: {str(e)}"}

TOOL = Tool(
    name="proactive_ops",
    summary="Proactive assistance - background monitoring, scheduled tasks, system health alerts, autonomous suggestions",
    plan=_plan,
    run=_run,
    permissions={"confirm": False}  # Monitoring is safe, suggestions are non-destructive
)

register(TOOL)

# Auto-start monitoring when tool is loaded
proactive_assistant.start_monitoring()
