# cmp-use (Unified Autonomous Agent)

- CLI: `cmpuse` (Typer)
- Module API: `cmpuse.agent`
- Optional HTTP API: `cmpuse.api`

## Quick Start

- Install deps: `pip install -r requirements.txt`
- List tools: `python -m cmpuse.cli tools`
- Plan: `python -m cmpuse.cli plan --json '{"tool": "json_ops", "args": {"operation":"validate","data":"{}"}}'`
- Run (dry-run default): `python -m cmpuse.cli run --json '{"tool":"boot_repair"}'`
- Force (apply changes): `python -m cmpuse.cli run --json '{"tool":"json_ops","args":{"operation":"merge","a":{},"b":{}}}' --force`
 - Retries/Timeouts: `python -m cmpuse.cli run --json '{"tool":"net_ops","args":{"url":"https://example.com"}}' --retries 2 --timeout 5 --force`

### Layered Planner Example

- `python -m cmpuse.cli run --json '{"tool":"layered_planner","args":{"goal":"Audit disks. Repair boot config. Verify success."}}'`

### Autonomous Mode

- `python -m cmpuse.cli auto --goal "Audit disks. Repair boot config. Verify success."`
  - Adds retries/timeouts by default; still dry-run unless `--force`.
  - Maps steps to tools: boot repair → `boot_repair` (preview), audit/verify → `sys_ops`, JSON tasks → `json_ops`.

## Safety

- Dry-run by default. Use `--force` to apply changes.
- Path whitelist for file operations (default: current directory).
- Network disabled by default; enable with `CMPUSE_NETWORK=1`.
- No shell execution unless explicitly enabled (future).

## API

- `uvicorn cmpuse.api:app --host 127.0.0.1 --port 8000`

## Planner Controls

- Retries: `--retries N` with exponential backoff (`--backoff`, `--backoff-factor`).
- Timeout: `--timeout SECONDS` per step.
- Interruption: create `~/.cmpuse/stop` file to abort before the next step.
