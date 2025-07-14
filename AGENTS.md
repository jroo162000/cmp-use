# Agents Overview

This document describes the distinct “agents” (components/microservices) in the **Jarvis-Like Layered Agent** architecture, their responsibilities, interfaces, and how they interoperate.

## 1. Commander Agent

**Role:** Central coordinator and chat interface.
**Location:** `commander/server.py`

### Responsibilities

* Receives user chat requests (HTTP REST & WebSocket).
* Invokes LLM (OpenAI or local) with function-calling schema.
* Dispatches function calls to Worker Agents.
* Records conversation history and function results.
* Exposes `/status`, `/chat`, `/task`, `/register`, `/result` endpoints.

### Key Modules

* **`planning.py`**: Breaks user goals into schedulable subtasks.
* **`status_ui/`**: React dashboard for real-time monitoring.
* **`server.py`**: FastAPI application wiring everything together.
w55z61-codex/run-all-code-from-the-repo
=======
* Depends on `cryptography` for encrypting worker results, even in minimal setups.
main

## 2. Worker Agent

**Role:** Executes individual skills on target machines.
**Location:** `worker/worker.py`, `worker/bootstrap.py`

### Responsibilities

* Auto-discovers skill modules under `worker/skills/`.
* Registers with Commander using bearer token.
* Polls `/task/{worker_id}` for new tasks.
* Executes skills (e.g., shell commands, diagnostics, sensor capture).
* Posts encrypted results back to Commander.

### Key Components

* **`bootstrap.py`**: Creates venv, installs deps, launches worker.
* **`skills/`**: Python modules decorated with `@skill`—`core.py`, `network.py`, `sensor.py`, etc.
w55z61-codex/run-all-code-from-the-repo
* **`sandbox.py`**: (Optional) Plugin isolation and validation.
=======
main

## 3. Planning Agent

**Role:** High-level goal decomposition and scheduling.
**Location:** `commander/planning.py`

### Responsibilities

* Receives abstract goals from Commander.
* Uses simple LLM prompts or heuristics to split into steps.
* Stores subtasks in SQLite DB with schedule timestamps.
* Provides due tasks for automatic enqueueing.

## 4. Memory Agent

**Role:** Persistent conversation memory.
w55z61-codex/run-all-code-from-the-repo
**Location:** `memory.py`
=======
**Location:** `memory_utils.py`
main

### Responsibilities

* Stores chat history in Redis or local store.
* Provides context to LLM calls (full dialogue or recent window).
* Supports retrieval, summarization, and session management.

## 5. Voice I/O Agent

**Role:** Handles speech input/output.
w55z61-codex/run-all-code-from-the-repo
**Location:** `voice_io.py`, `tts.py`
=======
**Location:** `voice_utils.py`
main

### Responsibilities

* **Speech-to-Text**: Uses Whisper to transcribe audio files.
* **Text-to-Speech**: Uses `pyttsx3` for voice responses.
* Exposes functions to the Commander for seamless multimodal chat.

## 6. Sensor Agent

**Role:** Captures real-time environmental data.
w55z61-codex/run-all-code-from-the-repo
**Location:** `worker/skills/sensor.py`
=======
**Location:** _(not yet implemented)_
main

### Responsibilities

* **Camera**: Grabs frames via OpenCV (`capture_image`).
* **Microphone**: Records audio with `sounddevice` (`record_audio`).
* Returns raw bytes or arrays for further processing by LLM or UI.

w55z61-codex/run-all-code-from-the-repo
## 7. Plugin Manager Agent

**Role:** Dynamic plugin loading and version control.
**Location:** `plugin_manager.py`, `worker/sandbox.py`

### Responsibilities

* Pulls new skill definitions from Git or URLs.
* Validates and installs in isolated venv or container.
* Updates skill registry in Worker Agent without full redeploy.

## 8. Local Model Agent

## 7. Local Model Agent
main

**Role:** Provides fallback LLM inference.
**Location:** `models/local_model.py`

### Responsibilities

* Wraps local inference engines (e.g., llama.cpp).
* Implements same `chat()` interface as OpenAI client.
* Commander selects between local or API-based LLM at runtime.

w55z61-codex/run-all-code-from-the-repo
## 9. System-Health UI Agent
=======
## 8. System-Health UI Agent
main

**Role:** Web dashboard for monitoring.
**Location:** `commander/status_ui/` React app

### Responsibilities

* Displays active Workers, queued tasks, and logs.
* Streams sensor data (camera snapshots, audio clips).
w55z61-codex/run-all-code-from-the-repo
* Allows manual task enqueueing and plugin management.
=======
* Allows manual task enqueueing and plugin management
  (`layered_agent_full/plugin_manager.py`).
main

---

**Extensibility:** Any new agent should conform to these patterns—define clear interfaces, register with the Commander’s schema, and expose tasks as function-calling endpoints.

**Next Steps:** Validate each agent with unit tests, integrate end-to-end workflows, and secure with role-based access controls.
