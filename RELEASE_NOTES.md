# Release Notes – 0.1.0

Highlights
- Unified autonomous agent package `cmpuse` (Python 3.11).
- CLI (Typer) and optional HTTP API (FastAPI).
- Safe-by-default operations: dry-run, whitelists, network opt-in.
- Planner with retries, timeouts, backoff, and interruption.

Breaking Changes
- None; this is an additive initial release of the unified package.

Known Limitations
- `boot_repair` performs preview-only; real repairs require explicit implementation and confirmations.
- `net_ops` is disabled unless `CMPUSE_NETWORK=1`.

Upgrade Guide
- Install: `pip install -r cmp-use/requirements.txt`
- CLI: `python -m cmpuse.cli --help`
- API: `uvicorn cmpuse.api:app --host 127.0.0.1 --port 8000`

