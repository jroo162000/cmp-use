# Agents Overview

6vfos9-codex/run-all-code-from-the-repo
This document describes the distinct **agents** (components/micro‑services) in the **Jarvis‑Like Layered Agent** architecture, their responsibilities, interfaces, and how they interoperate.

## 1. Commander Agent

| **Item** | **Details** |
| --- | --- |
| **Role** | Central coordinator & chat API |
| **Code Location** | `commander/server.py` |
| **Key Endpoints** | `/status`, `/chat`, `/task`, `/register`, `/result` |
| **Depends On** | `cryptography` (encrypting worker payloads), `planning.py`, React **`status_ui/`** |

### Responsibilities
1. Accept chat via REST or WebSocket.  
2. Call the primary LLM (OpenAI or local fallback) using **function‑calling**.  
3. Route function calls to the correct Worker.  
4. Persist chat history & function results.  
5. Expose a health/status API for the dashboard.

---

## 2. Worker Agent

| **Item** | **Details** |
| --- | --- |
| **Role** | Executes skills on the host machine |
| **Code Location** | `worker/worker.py`, `worker/bootstrap.py` |
| **Key Directories** | `worker/skills/`, optional `worker/sandbox.py` |

### Responsibilities
* Discover skills decorated with `@skill`.  
* Register with Commander using bearer‑token auth.  
* Poll for tasks → execute → POST encrypted result.  
* Optional plugin isolation via **`sandbox.py`**.

---

## 3. Planning Agent

| **Role** | Decomposes high‑level goals into scheduled subtasks |
| **Code** | `commander/planning.py` |

Uses simple rules / LLM prompts → stores tasks in SQLite → exposes "due" tasks for enqueueing.

---

## 4. Memory Agent

| **Role** | Persistent chat/session memory |
| **Code** | `memory_utils.py` (Redis‑backed) |

Stores full dialogue, supplies context windows, supports summarisation.

---

## 5. Voice I/O Agent

| **Role** | Speech → text (Whisper) & text → speech (pyttsx3) |
| **Code** | `voice_utils.py` |

---

## 6. Sensor Agent

| **Role** | Camera & microphone capture |
| **Code** | `worker/skills/sensor.py` |

Functions: `capture_image`, `record_audio` ; returns bytes/arrays for upstream processing.

---

## 7. Plugin‑Manager Agent

| **Role** | Dynamic plugin loading & version control |
| **Code** | `plugin_manager.py`, `worker/sandbox.py` |

Pulls skill modules from Git/URLs ➜ validates ➜ installs in isolated venv/container ➜ hot‑reloads Worker registry.

---

## 8. Local‑Model Agent

| **Role** | Fallback on‑prem LLM inference |
| **Code** | `models/local_model.py` |

Wraps e.g. **llama.cpp** with a `chat()` interface identical to OpenAI.

---

## 9. System‑Health UI Agent

| **Role** | Web dashboard for real‑time monitoring |
| **Code** | `commander/status_ui/` (React) |

Displays Workers, task queue, logs, sensor feeds; allows manual task enqueues & plugin ops.

---

### Extensibility Guidelines
* New agents must expose a clear API (HTTP, WebSocket, or function‑call schema).  
* Register skills with Commander so they appear in `function_schema`.  
* Add unit‑tests & role‑based permissions before deployment.

---

**Next Steps** → Write integration tests, wire RBAC, and containerise Worker for OS independence.
=======
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
c6btom-codex/run-all-code-from-the-repo
=======
w55z61-codex/run-all-code-from-the-repo
=======
* Depends on `cryptography` for encrypting worker results, even in minimal setups.
main
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
c6btom-codex/run-all-code-from-the-repo
* **`sandbox.py`**: (Optional) Plugin isolation and validation.
=======
w55z61-codex/run-all-code-from-the-repo
* **`sandbox.py`**: (Optional) Plugin isolation and validation.
=======
main
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
c6btom-codex/run-all-code-from-the-repo
**Location:** `memory.py`
=======
w55z61-codex/run-all-code-from-the-repo
**Location:** `memory.py`
=======
**Location:** `memory_utils.py`
main
main

### Responsibilities

* Stores chat history in Redis or local store.
* Provides context to LLM calls (full dialogue or recent window).
* Supports retrieval, summarization, and session management.

## 5. Voice I/O Agent

**Role:** Handles speech input/output.
c6btom-codex/run-all-code-from-the-repo
**Location:** `voice_io.py`, `tts.py`
=======
w55z61-codex/run-all-code-from-the-repo
**Location:** `voice_io.py`, `tts.py`
=======
**Location:** `voice_utils.py`
main
main

### Responsibilities

* **Speech-to-Text**: Uses Whisper to transcribe audio files.
* **Text-to-Speech**: Uses `pyttsx3` for voice responses.
* Exposes functions to the Commander for seamless multimodal chat.

## 6. Sensor Agent

**Role:** Captures real-time environmental data.
c6btom-codex/run-all-code-from-the-repo
**Location:** `worker/skills/sensor.py`
=======
w55z61-codex/run-all-code-from-the-repo
**Location:** `worker/skills/sensor.py`
=======
**Location:** _(not yet implemented)_
main
main

### Responsibilities

* **Camera**: Grabs frames via OpenCV (`capture_image`).
* **Microphone**: Records audio with `sounddevice` (`record_audio`).
* Returns raw bytes or arrays for further processing by LLM or UI.

c6btom-codex/run-all-code-from-the-repo
=======
w55z61-codex/run-all-code-from-the-repo
main
## 7. Plugin Manager Agent

**Role:** Dynamic plugin loading and version control.
**Location:** `plugin_manager.py`, `worker/sandbox.py`

### Responsibilities

* Pulls new skill definitions from Git or URLs.
* Validates and installs in isolated venv or container.
* Updates skill registry in Worker Agent without full redeploy.

## 8. Local Model Agent

c6btom-codex/run-all-code-from-the-repo
=======
## 7. Local Model Agent
main

main
**Role:** Provides fallback LLM inference.
**Location:** `models/local_model.py`

### Responsibilities

* Wraps local inference engines (e.g., llama.cpp).
* Implements same `chat()` interface as OpenAI client.
* Commander selects between local or API-based LLM at runtime.

c6btom-codex/run-all-code-from-the-repo
## 9. System-Health UI Agent
=======
w55z61-codex/run-all-code-from-the-repo
## 9. System-Health UI Agent
=======
## 8. System-Health UI Agent
main
main

**Role:** Web dashboard for monitoring.
**Location:** `commander/status_ui/` React app

### Responsibilities

* Displays active Workers, queued tasks, and logs.
* Streams sensor data (camera snapshots, audio clips).
c6btom-codex/run-all-code-from-the-repo
* Allows manual task enqueueing and plugin management.
=======
w55z61-codex/run-all-code-from-the-repo
* Allows manual task enqueueing and plugin management.
=======
* Allows manual task enqueueing and plugin management
  (`layered_agent_full/plugin_manager.py`).
main
main

---

**Extensibility:** Any new agent should conform to these patterns—define clear interfaces, register with the Commander’s schema, and expose tasks as function-calling endpoints.

**Next Steps:** Validate each agent with unit tests, integrate end-to-end workflows, and secure with role-based access controls.
main
