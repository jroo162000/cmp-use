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

The packages include `scikit-learn`, `transformers` and other heavy
dependencies, so installation may take some time.

## Running the scripts

### `app.py`

Start the Flask server:

```bash
python app.py
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
python boot_repair.py
```

You can pass `--testmode` to perform a quick start-up test without entering the
full repair loop:

```bash
python boot_repair.py --testmode
```

## Safety notice

`boot_repair.py` performs patch-based self modification. Unintended behavior can
occur if a generated patch is faulty. Review the code and run it only on systems
where potential changes and restarts are acceptable.
