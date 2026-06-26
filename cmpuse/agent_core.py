from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import concurrent.futures
import time
import os

from .config import Config
from .tool_registry import get_tool
from .cmp_logging import event_log


@dataclass
class Step:
    tool: str
    args: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    steps: List[Step]


class Agent:
    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config.from_env()

    def plan(self, goal: Dict[str, Any]) -> Plan:
        # Minimal planner: accept explicit steps or a single tool goal
        steps: List[Step] = []
        if "steps" in goal:
            for s in goal["steps"]:
                steps.append(Step(tool=s["tool"], args=s.get("args", {})))
        elif "tool" in goal:
            steps.append(Step(tool=goal["tool"], args=goal.get("args", {})))
        else:
            raise ValueError("Unsupported goal format; provide 'tool' or 'steps'")
        return Plan(steps=steps)

    def run(
        self,
        plan: Plan,
        force: bool = False,
        retries: int = 0,
        timeout_sec: Optional[float] = None,
        backoff_initial: float = 0.5,
        backoff_factor: float = 2.0,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        stop_file = os.path.join(os.path.expanduser("~"), ".cmpuse", "stop")
        os.makedirs(os.path.dirname(stop_file), exist_ok=True)

        for idx, step in enumerate(plan.steps, start=1):
            tool = get_tool(step.tool)
            if not tool:
                results.append({"status": "error", "message": f"unknown tool {step.tool}"})
                continue

            # Interruption point
            if os.path.exists(stop_file):
                results.append({"status": "aborted", "message": "stop file present", "tool": step.tool})
                break

            preview = tool.plan(step.args)
            event_log_logger = __import__("logging").getLogger("cmpuse.agent")
            event_log(event_log_logger, "step_preview", step_index=idx, tool=step.tool, preview=preview)

            if self.config.dry_run and not force:
                results.append({"status": "dry-run", "tool": step.tool, "preview": preview})
                continue

            attempt = 0
            delay = backoff_initial
            last_error: Optional[str] = None

            while True:
                attempt += 1

                def _invoke():
                    return tool.run(step.args, dry_run=not force)

                if timeout_sec and timeout_sec > 0:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        fut = pool.submit(_invoke)
                        try:
                            res = fut.result(timeout=timeout_sec)
                        except concurrent.futures.TimeoutError:
                            fut.cancel()
                            res = {"status": "timeout", "message": f"step exceeded {timeout_sec}s"}
                else:
                    try:
                        res = _invoke()
                    except Exception as e:  # pragma: no cover (defensive)
                        res = {"status": "error", "message": str(e)}

                if res.get("status") in {"ok", "dry-run"}:
                    event_log(event_log_logger, "step_success", step_index=idx, tool=step.tool, result=res)
                    results.append({"tool": step.tool, **res})
                    break

                # Not ok: decide on retry
                last_error = res.get("message") or res.get("status")
                if attempt > retries:
                    event_log(event_log_logger, "step_failed", step_index=idx, tool=step.tool, result=res, attempts=attempt)
                    results.append({"tool": step.tool, **res, "attempts": attempt})
                    break
                event_log(event_log_logger, "step_retry", step_index=idx, tool=step.tool, attempt=attempt, delay=delay, reason=last_error)
                time.sleep(max(0.0, delay))
                delay *= backoff_factor

        return results
