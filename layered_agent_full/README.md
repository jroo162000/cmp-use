# Layered Agent

This directory contains a minimal demo of the Commander/Worker architecture. Follow the steps below to run it locally.

## 1. Install dependencies

Create (or activate) a virtual environment and install the required packages:

```bash
pip install -r requirements.txt
# or for a slimmer set
pip install -r requirements-minimal.txt
```
Installing the full requirements fetches some packages from GitHub (for
example the `whisper` repository), so it needs outbound network
connectivity. If your environment restricts internet access, install the
minimal requirements instead or skip those optional capabilities.

Optional sensor features (camera, microphone) require extra packages:

```bash
pip install opencv-python sounddevice numpy
```

## 2. Set environment variables

The commander uses OpenAI for language-model calls. Define at least `OPENAI_API_KEY` before starting the server. Workers optionally use `VAULT_PASSPHRASE` to encrypt results.

```bash
export OPENAI_API_KEY=your_openai_key
export VAULT_PASSPHRASE=optional_passphrase  # optional
```

These values can also be placed in `~/.config/agent/secrets.toml`.

## 3. Start the Commander

Run the FastAPI server on port 8000:

```bash
python -m layered_agent_full.commander.server --port 8000
```

On startup the server prints a registration token. Copy this token; it will be required by workers.

## 4. Launch a Worker

In a separate terminal run the worker module directly (after installing its dependencies):

```bash
python layered_agent_full/worker/worker.py --server http://localhost:8000 --layer L-3 --token <token>
```

Replace `<token>` with the value displayed by the commander. The worker will register with the server and begin polling for tasks.

Alternatively you can use the helper bootstrap script which creates a virtual environment for the worker automatically:

```bash
python -m layered_agent_full.worker.bootstrap --server http://localhost:8000 --token <token>
```

