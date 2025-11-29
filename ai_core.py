# ai_core.py
import os
from pathlib import Path
from openai import OpenAI

GLOBAL_KEY_PATH = Path.home() / ".nio_openai_key"

def load_openai_key() -> str:
    # 1) First try environment variable (for deployment)
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key.strip()

    # 2) Fallback to local file (for development)
    if GLOBAL_KEY_PATH.exists():
        key = GLOBAL_KEY_PATH.read_text(encoding="utf-8").strip()
        if key:
            return key

    raise RuntimeError(
        "No OpenAI key found. Set OPENAI_API_KEY environment variable or create ~/.nio_openai_key file."
    )

def get_openai_client() -> OpenAI:
    return OpenAI(api_key=load_openai_key())