# Tools Registry

- Contract:
  - plan(args) -> preview dict
  - run(args, dry_run: bool) -> result dict
- Safety:
  - All tools must honor dry_run and avoid destructive actions unless forced.
  - Provide permissions metadata (e.g., requires_admin, destructive) where applicable.

## Included Tools (13 Total)

### File & System Operations
- **boot_repair**: Analyze boot configuration and suggest safe fixes (preview-only for now).
- **json_ops**: Validate or merge JSON payloads.
- **fs_ops**: Read/write with path whitelist; writes gated by dry-run.
- **sys_ops**: Non-destructive system info (CPU, memory, storage, OS details).
- **ps_exec**: Execute PowerShell commands and scripts.
- **open_item**: Open files and URLs with default system applications.

### Network & Web
- **net_ops**: Minimal HTTP GET; disabled unless CMPUSE_NETWORK=1.
- **browser_automation**: Complete visible browser automation using Selenium (launch, navigate, click, type).

### Device Control (Added Dec 13, 2025)
- **mouse_ops**: Control mouse cursor - move, click, double-click, right-click, drag, scroll, position tracking.
- **key_ops**: Keyboard control - type text, press keys, hotkey combinations (Ctrl+C, etc.), hold/release keys.
- **screen_ops**: Screen operations - screenshots (full/region), locate images, pixel colors, screen dimensions.

### Planning & Memory
- **layered_planner**: Multi-step task planning and execution.
- **memory_system**: Conversation memory, context storage, user profile learning.

