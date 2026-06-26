# Changelog

## 0.1.0 – Unify repository into one autonomous agent

- New package `cmpuse` with agent core, tool registry, tools, CLI, and optional HTTP API.
- Safety-first defaults: dry-run, path whitelist, network disabled.
- Planner features: retries, timeouts, exponential backoff, interruption guard.
- Tools: boot_repair (preview), json_ops, fs_ops, net_ops, sys_ops, layered_planner.
- Tests added and wired in CI (GitHub Actions).
- Docs: README, ARCHITECTURE, TOOLS.

