# feat: unify repository into one autonomous agent (CLI+API, tools, tests, docs)

## Overview
This PR unifies the repository into a single autonomous agent package `cmpuse` (Python 3.11) with a clean architecture, safe defaults, CLI and optional HTTP API, tests, and CI.

- Language: Python 3.11
- Packaging: pip + requirements.txt (Poetry optional)
- Entrypoints: CLI (`cmpuse` via `python -m cmpuse.cli`) and module API; optional FastAPI server
- Safety: dry-run by default; destructive/system actions require `--force` or explicit confirmation

## Architecture (ASCII)
```
cmpuse/
  __init__.py
  agent_core.py        # plan–act–observe loop; retries, timeouts, interruption
  tool_registry.py     # tool contracts + registry
  tools/
    __init__.py
    boot_repair.py     # preview-only boot repair wrapper (safe)
    json_ops.py        # validate/merge JSON
    fs_ops.py          # whitelist + dry-run file ops
    net_ops.py         # HTTP GET (disabled by default)
    sys_ops.py         # non-destructive system info
    layered_planner.py # split goal into ordered steps
  cli.py               # Typer CLI: tools, plan, run, describe, version
  api.py               # FastAPI: /health, /tools, /plan, /run
  config.py            # env-based safe defaults
  logging.py           # structured logs with secret redaction
```

## What’s Included
- Safe-by-default operations (dry-run, path whitelist, network opt-in)
- Planner controls: retries, exponential backoff, per-step timeouts, interruption file (`~/.cmpuse/stop`)
- Tools integrated with consistent contracts (plan/run, dry-run aware)
- Tests covering core planner, tools, and CLI
- GitHub Actions CI to run tests on Python 3.11
- Documentation: README, ARCHITECTURE, TOOLS, CHANGELOG, RELEASE_NOTES

## Safety & Guardrails
- Dry-run by default; use `--force` for writes/repairs
- Path whitelist for FS ops (`CMPUSE_PATH_WHITELIST`); denies outside by default
- Network calls disabled unless `CMPUSE_NETWORK=1`
- Secret redaction in logs; no shelling out by default

## How To Run
- Install: `pip install -r cmp-use/requirements.txt`
- CLI: `python -m cmpuse.cli --help`
- List tools: `python -m cmpuse.cli tools`
- Plan: `python -m cmpuse.cli plan --json '{"tool":"json_ops","args":{"operation":"validate","data":"{}"}}'`
- Run (dry-run): `python -m cmpuse.cli run --json '{"tool":"boot_repair"}'`
- Force: `python -m cmpuse.cli run --json '{"tool":"json_ops","args":{"operation":"merge","a":{},"b":{}}}' --force`
- API: `uvicorn cmpuse.api:app --host 127.0.0.1 --port 8000`

## Tests & CI
- Run tests: `cd cmp-use && pytest -q`
- CI: `.github/workflows/ci.yml` (Python 3.11) installs `cmp-use/requirements.txt` and runs `pytest`

## Limitations / Follow-ups
- `boot_repair` currently preview-only; real repairs should be implemented behind explicit confirms and `--force`, with admin checks
- Consider adding: Dockerfile/compose, short-term state at `~/.cmpuse/state.json`, LLM abstraction `cmpuse/llm.py`, explicit shell permission flag

## Checklist
- [x] Package `cmpuse` added (CLI, API, tools, config, logging)
- [x] Tests added and CI wired
- [x] Safe defaults and guardrails
- [x] Docs updated (README, ARCHITECTURE, TOOLS, CHANGELOG, RELEASE_NOTES)

## Test Summary (local)
- Unit + scenario tests pass locally with Python 3.11
- CI workflow included to validate in PR

---

> Acceptance criteria: importable `cmpuse` with CLI/API, destructive ops gated by dry-run/confirm, tests running in CI, docs for autonomous vs guided mode.

