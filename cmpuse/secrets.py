from __future__ import annotations

import json
import os
from typing import Dict

SECRETS_DIR = os.path.join(os.path.expanduser("~"), ".cmpuse")
SECRETS_PATH = os.path.join(SECRETS_DIR, "secrets.json")


def load_into_env() -> Dict[str, str]:
    """Load secrets from ~/.cmpuse/secrets.json into os.environ if not already set.

    The file should be a JSON object, e.g.:
      {
        "OPENAI_API_KEY": "sk-...",
        "CMPUSE_LLM_MODEL": "gpt-5",
        "CMPUSE_LLM_MAX_TOKENS": "8000"
      }
    """
    loaded: Dict[str, str] = {}
    try:
        if not os.path.exists(SECRETS_PATH):
            return loaded
        with open(SECRETS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return loaded
        for k, v in data.items():
            if isinstance(k, str) and isinstance(v, str) and not os.getenv(k):
                os.environ[k] = v
                loaded[k] = v
    except Exception:
        # Do not raise; secret loading failure should not crash app
        return loaded
    return loaded

