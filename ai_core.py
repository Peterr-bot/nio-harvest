# ai_core.py
import os
from pathlib import Path
from openai import OpenAI

GLOBAL_KEY_PATH = Path.home() / ".nio_openai_key"

def load_openai_key() -> str:
    # 1) Prefer the global file
    if GLOBAL_KEY_PATH.exists():
        key = GLOBAL_KEY_PATH.read_text(encoding="utf-8").strip()
        if key:
            return key

    # 2) Fallback to env var if file missing
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key.strip()

    raise RuntimeError(
        "No OpenAI key found. Create ~/.nio_openai_key or set OPENAI_API_KEY."
    )

def get_openai_client() -> OpenAI:
    return OpenAI(api_key=load_openai_key())