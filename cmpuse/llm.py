from __future__ import annotations

import os
from typing import Optional

from .secrets import load_into_env


def is_configured() -> bool:
    load_into_env()
    return bool(os.getenv("OPENAI_API_KEY"))


def default_model() -> str:
    # Allow override; otherwise pick a capable default
    load_into_env()
    return os.getenv("CMPUSE_LLM_MODEL", "gpt-4o")


def _max_tokens_default() -> int:
    try:
        load_into_env()
        v = os.getenv("CMPUSE_LLM_MAX_TOKENS")
        if v:
            return int(v)
    except Exception:
        pass
    return 8000


def answer(prompt: str, system: Optional[str] = None, model: Optional[str] = None) -> str:
    load_into_env()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "LLM is not configured. Set OPENAI_API_KEY (or in ~/.cmpuse/secrets.json)."
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return "OpenAI client not installed. Please `pip install openai`."

    client = OpenAI(api_key=api_key)
    mdl = (model or default_model()).strip()
    sys_msg = system or (
        "You are AVa, a helpful, concise assistant."
        " Respond directly to the user's question."
        " Prefer short, clear answers."
    )
    max_tokens = _max_tokens_default()

    try:
        # Use standard chat completions API - just use max_tokens for compatibility
        resp = client.chat.completions.create(
            model=mdl,
            messages=[
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt},
            ],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"LLM error: {e}"
