# Boot Repair Assistant

This repository contains two Python demonstration scripts.

## Scripts

- **`app.py`** – A minimal Flask application. It exposes endpoints to open a
  browser and to simulate a keystroke using `xdotool`. An earlier endpoint for
  executing arbitrary code has been purposely disabled.
- **`boot_repair.py`** – An experimental self-healing assistant that attempts to
  repair boot issues. It can apply patches to its own source code based on
  suggestions from a language model. Because it modifies itself at run time,
  **use it only in a controlled or disposable environment.**

## Installation

Python 3.9 or newer is recommended. Create a virtual environment and install the
dependencies listed in `requirements.txt`:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use .venv\Scripts\activate
pip install -r requirements.txt
```

Only the core dependencies are installed this way. Optional GPU-intensive
packages (such as `vllm`) are listed in `requirements-gpu.txt` and can be
installed separately if needed:

```bash
pip install -r requirements-gpu.txt  # optional
```

The packages include `scikit-learn`, `transformers` and other heavy
dependencies, so installation may take some time.

## Environment variables and system packages

Some features require additional settings and packages.

- `DEEPSEEK_API_KEY` must be defined so the assistant can access the language model. Export it before running the scripts:

```bash
export DEEPSEEK_API_KEY=your_token_here
```

- The utilities `patch`, `xdotool` and `Xvfb` must be installed. On Debian/Ubuntu systems run:

```bash
sudo apt-get install patch xdotool xvfb
```

On other distributions use the appropriate package manager such as `dnf` or `pacman`.


## Running the scripts

Run each entry point using ``python -m`` so that the project root
is placed on ``PYTHONPATH`` automatically. This avoids modifying
``sys.path`` in code.

### `app.py`

Start the Flask server:

```bash
python -m app
```

The server listens on port 5000. Available endpoints:

- `POST /open_browser` – opens the default browser at Google.
- `POST /simulate_keystroke` – send a key press, e.g. `{ "key": "Return" }`.
- `POST /run_code` – returns HTTP 403 because remote code execution is disabled.

### `boot_repair.py`

This script launches an interactive console for diagnosing and repairing boot
issues. It also contains logic to modify and patch its own code. For safety run
it inside a VM or other sandbox.

```bash
python -m boot_repair
```

You can pass `--testmode` to perform a quick start-up test without entering the
full repair loop:

```bash
python -m boot_repair --testmode
```

To enable experimental voice interaction, run with `--voice` (requires
`SpeechRecognition` and `pyttsx3`):

```bash
python -m boot_repair --voice
```

## Safety notice

`boot_repair.py` performs patch-based self modification. Unintended behavior can
occur if a generated patch is faulty. Review the code and run it only on systems
where potential changes and restarts are acceptable.
Before a patch suggested by the language model is applied, the script shows the diff and asks for confirmation (`y`/`n`).

## Layered Agent demo

The `layered_agent_full` folder contains a proof-of-concept Commander/Worker architecture. It can be run independently from the boot-repair scripts.

### Installing requirements

Create or activate a virtual environment and install the dependencies. The full set of packages is in `layered_agent_full/requirements.txt`. A smaller set is available in `layered_agent_full/requirements-minimal.txt`.

```bash
pip install -r layered_agent_full/requirements.txt
# or
pip install -r layered_agent_full/requirements-minimal.txt
```

### Starting the Commander

Run the FastAPI server:

```bash
python -m layered_agent_full.commander.server
```

The server prints the registration token required by workers.

### Launching a Worker

Start a worker and point it at the commander:

```bash
python -m layered_agent_full.worker.worker --server http://localhost:8000 --layer L-2 --token <token>
```

`bootstrap.py` can also be used to create a dedicated virtual environment before launching:

```bash
python -m layered_agent_full.worker.bootstrap --server http://localhost:8000 --token <token>
```

### Environment variables

Set `OPENAI_API_KEY` so the commander can access the language model. Workers use `VAULT_PASSPHRASE` if defined to encrypt task results. These values may also be stored in `~/.config/agent/secrets.toml`:

```toml
openai_api_key = "YOUR_OPENAI_KEY"
vault_passphrase = "optional passphrase"
```

