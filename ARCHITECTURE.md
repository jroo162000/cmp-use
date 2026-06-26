# Architecture

- Agent Core: plan–act–observe loop with dry-run default and force gating.
- Tool Registry: consistent interface for tools; validation and permissions metadata.
- Tools: boot_repair (preview-only), json_ops, fs_ops (whitelist, dry-run), net_ops (disabled by default), sys_ops.
- CLI: Typer app with `plan`, `run`, `tools`, `describe`.
- API: FastAPI with `/plan`, `/run`, `/tools`, and `/health`.
- Config: environment-driven safe defaults.
- Logging: structured, with secret redaction.

