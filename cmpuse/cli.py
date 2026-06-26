from __future__ import annotations

import json
import sys
from pathlib import Path
import typer

from .agent_core import Agent
from .config import Config
from .tool_registry import list_tools, get_tool
from . import __version__
from .cmp_logging import setup_logging
from .agent_core import Plan, Step


app = typer.Typer(help="cmpuse CLI - unified autonomous agent")


def _load_json_arg(json_arg: str | None, file: Path | None) -> dict:
    if json_arg:
        return json.loads(json_arg)
    if file:
        return json.loads(Path(file).read_text(encoding="utf-8"))
    data = sys.stdin.read()
    return json.loads(data) if data else {}


@app.callback()
def main(ctx: typer.Context, verbose: bool = typer.Option(False, "--verbose", help="verbose logs")):
    setup_logging("DEBUG" if verbose else "INFO")


@app.command()
def tools() -> None:
    """List available tools."""
    for name, tool in list_tools().items():
        typer.echo(f"- {name}: {tool.summary}")


@app.command()
def plan(json_str: str = typer.Option(None, "--json"), file: Path = typer.Option(None, "--file")) -> None:
    goal = _load_json_arg(json_str, file)
    agent = Agent()
    p = agent.plan(goal)
    typer.echo(json.dumps({"steps": [s.__dict__ for s in p.steps]}, indent=2))


@app.command()
def run(
    json_str: str = typer.Option(None, "--json"),
    file: Path = typer.Option(None, "--file"),
    force: bool = typer.Option(False, "--force", help="apply changes (disable dry-run)"),
    retries: int = typer.Option(0, "--retries", help="retry failed steps N times"),
    timeout: float = typer.Option(None, "--timeout", help="per-step timeout seconds"),
    backoff: float = typer.Option(0.5, "--backoff", help="initial backoff seconds"),
    backoff_factor: float = typer.Option(2.0, "--backoff-factor", help="backoff multiplier"),
) -> None:
    goal = _load_json_arg(json_str, file)
    cfg = Config.from_env()
    agent = Agent(cfg)
    p = agent.plan(goal)
    res = agent.run(p, force=force, retries=retries, timeout_sec=timeout, backoff_initial=backoff, backoff_factor=backoff_factor)
    typer.echo(json.dumps(res, indent=2))


@app.command()
def describe(tool: str) -> None:
    t = get_tool(tool)
    if not t:
        raise typer.Exit(code=1)
    typer.echo(json.dumps({"name": t.name, "summary": t.summary}, indent=2))


@app.command()
def version() -> None:
    typer.echo(__version__)


def entrypoint():
    app()


@app.command()
def auto(
    goal: str = typer.Option(None, "--goal", help="Natural language goal (e.g., 'Audit disks. Repair boot.')"),
    file: Path = typer.Option(None, "--file", help="Text file containing the goal"),
    force: bool = typer.Option(False, "--force", help="apply changes (disable dry-run)"),
    retries: int = typer.Option(1, "--retries", help="retry failed steps N times"),
    timeout: float = typer.Option(30.0, "--timeout", help="per-step timeout seconds"),
    backoff: float = typer.Option(0.5, "--backoff", help="initial backoff seconds"),
    backoff_factor: float = typer.Option(2.0, "--backoff-factor", help="backoff multiplier"),
) -> None:
    """Autonomous mode: plan from a natural-language goal, then execute."""
    cfg = Config.from_env()
    agent = Agent(cfg)

    # Load goal text
    if not goal and file:
        goal = file.read_text(encoding="utf-8")
    if not goal:
        data = sys.stdin.read()
        goal = data.strip()
    if not goal:
        typer.secho("Provide --goal, --file, or stdin text.", fg=typer.colors.RED)
        raise typer.Exit(code=2)

    # Use layered_planner to split into steps
    lp = get_tool("layered_planner")
    if not lp:
        typer.secho("layered_planner tool not found", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    lp_res = lp.run({"goal": goal}, dry_run=False)
    steps_text = lp_res.get("steps", [])

    def map_step(text: str) -> Step:
        t = text.lower()
        if ("boot" in t) and ("repair" in t or "bcd" in t):
            return Step(tool="boot_repair", args={})
        if any(k in t for k in ["audit", "system", "info", "verify", "check"]):
            return Step(tool="sys_ops", args={})
        if "json" in t and "merge" in t:
            return Step(tool="json_ops", args={"operation": "merge", "a": {}, "b": {}})
        if "json" in t and any(k in t for k in ["validate", "lint", "check"]):
            return Step(tool="json_ops", args={"operation": "validate", "data": "{}"})
        # Fallback: collect system info as a safe default
        return Step(tool="sys_ops", args={})

    steps = [map_step(s) for s in steps_text] or [Step(tool="sys_ops", args={})]
    p = Plan(steps=steps)

    # Preview planned steps
    preview = [{"tool": s.tool, "args": s.args} for s in steps]
    typer.secho("Planned steps:", fg=typer.colors.CYAN)
    typer.echo(json.dumps(preview, indent=2))

    # Execute
    res = agent.run(
        p,
        force=force,
        retries=retries,
        timeout_sec=timeout,
        backoff_initial=backoff,
        backoff_factor=backoff_factor,
    )
    typer.echo(json.dumps(res, indent=2))
