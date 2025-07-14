# Agents Overview

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
