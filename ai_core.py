# ai_core.py
import os
from pathlib import Path
from openai import OpenAI
import streamlit as st

GLOBAL_KEY_PATH = Path.home() / ".nio_openai_key"

def load_openai_key() -> str:
    # 1) Streamlit Cloud secrets (primary for deployment)
    try:
        return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass

    # 2) Environment variable (backup for deployment)
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key.strip()

    # 3) Local dev key file (development only)
    if GLOBAL_KEY_PATH.exists():
        key = GLOBAL_KEY_PATH.read_text(encoding="utf-8").strip()
        if key:
            return key

    raise RuntimeError(
        "No OpenAI key found. Add OPENAI_API_KEY to Streamlit secrets or environment variables."
    )

def get_openai_client() -> OpenAI:
    return OpenAI(api_key=load_openai_key())