````markdown
# Layered Chat-Driven Self-Healing Agent

This repository contains a layered, chat-driven autonomous agent with separate Commander and Worker components. It’s designed to run in rescue environments (Ubuntu shell, Windows PE) and self-heal by diagnosing and repairing boot issues, managing dependencies, and dynamically extending its own capabilities.

## Directory Layout

```bash
layered_agent/
├── requirements.txt             # full dependencies
├── requirements-minimal.txt     # fallback dependencies
├── commander/
│   └── server.py                # FastAPI chat interface & task router
├── shared/
│   ├── utils.py                 # secrets loading, AES decrypt
│   ├── protocol.py              # Pydantic models for chat & function calls
│   └── state.py                 # CommanderState with task queues & history
├── worker/
│   ├── bootstrap.py             # layered venv setup & worker launcher
│   ├── worker.py                # skill discovery, registration, polling loop
│   └── skills/
│       ├── core.py              # basic run_shell, download, install_package
│       ├── linux_diag.py        # collect_partition_info, collect_efi_status
│       ├── image_helper.py      # create_disk_image
│       ├── hardware_diag.py     # smart_status
│       ├── windows_boot.py      # fix_bootloader
│       └── qb_utils.py          # QuickBooks backup/compress utilities
└── README.md                    # this file
````

## Prerequisites

* **Python ≥ 3.9** (3.11 recommended)
* **Git**
* **Commander host**:

  * ChromeDriver in `PATH` (for headless browser skills)
* **Windows Worker**:

  * Visual C++ Build Tools (for pip wheels)
* **Linux Worker**:

  * `build-essential` (for pip wheels)
* **Network access**:

  * Worker must reach Commander (`:8000` or chosen port)
  * Commander must reach OpenAI API (for GPT calls)

## Setup

1. **Clone or unzip** this repo on your Commander machine.
2. **Install full dependencies**:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Configure OpenAI key**:

   * Copy `commander/secrets.toml.example` to `~/.config/agent/secrets.toml`
   * Edit it to include:

     ```toml
     openai_api_key = "sk-…"
     ```

## Running the Commander

```bash
source .venv/bin/activate
python commander/server.py --port 8000
```

You’ll see:

```
Commander listening on port 8000, bearer token: <YOUR_TOKEN>
```

Keep that token handy for Workers.

## Running a Worker

On each target (Linux or Windows PE):

1. **Ensure** Python is installed.
2. **Clone** or copy `worker/` and `requirements-minimal.txt` to the target.
3. **Export** the token:

   ```bash
   export AGENT_TOKEN=<YOUR_TOKEN>
   ```
4. **Run bootstrap**:

   ```bash
   python worker/bootstrap.py --server http://<COMMANDER_HOST>:8000 --token $AGENT_TOKEN
   ```

This creates a venv, installs deps, registers the Worker, and begins polling.

## Using the Agent

### Chat Interface

Send natural‐language commands to the Commander’s `/chat` endpoint:

```bash
curl -X POST http://<COMMANDER_HOST>:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message":"run_shell uname -a"}'
```

* **Commander** enqueues the `run_shell` task.
* **Worker** executes it and reports back.
* **Follow-up**:

  ```bash
  curl -X POST http://<COMMANDER_HOST>:8000/chat \
       -H "Content-Type: application/json" \
       -d '{"message":"what did run_shell return?"}'
  ```

### Status & Health

Check Worker health and registered skills:

```bash
curl http://<COMMANDER_HOST>:8000/status
```

### File Uploads

You can also upload files (e.g., custom scripts) via:

```bash
curl -X POST http://<COMMANDER_HOST>:8000/upload \
     -F "file=@script.ps1"
```

## Extending with New Skills

Add a module in `worker/skills/`, e.g.:

```python
from skills.core import skill

@skill
def my_new_skill(param: str) -> dict:
    """Does something useful."""
    # your code...
    return {"result": "done"}
```

Restart the Worker; the new skill is auto-discovered.

## Advanced Tips

* **Session persistence**: run under `tmux` or `screen` to keep processes alive across SSH sessions.
* **Multi-OS flow**: Workers register their OS (`linux` or `windows`); Commander routes tasks accordingly.
* **Safety rails**: destructive actions prompt for confirmation if `confirm_destructive = true` in `agent.toml`.
* **Plugin versioning**: plugins auto-committed to `plugins/.git` for rollback and audit.

---

Happy automating! Let me know if you need more details or further customization.
