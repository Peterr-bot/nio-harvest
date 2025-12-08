# ai_core.py
import os
from pathlib import Path
from openai import OpenAI
import streamlit as st

GLOBAL_KEY_PATH = Path.home() / ".nio_openai_key"

def load_openai_key() -> str:
    # 1. Streamlit Cloud secrets (primary for deployment)
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"].strip()
    except Exception:
        pass

    # 2. Environment variable (backup for deployment)
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key.strip()

    # 3. Local key file (development only - never on server)
    try:
        if GLOBAL_KEY_PATH.exists():
            return GLOBAL_KEY_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        pass

    raise RuntimeError(
        "No OpenAI key found. Set OPENAI_API_KEY in Streamlit secrets or local env."
    )

def get_openai_client() -> OpenAI:
    return OpenAI(api_key=load_openai_key())

def test_streamlit_secrets():
    """Test function to validate Streamlit secrets are readable"""
    try:
        if "OPENAI_API_KEY" in st.secrets:
            key = st.secrets["OPENAI_API_KEY"]
            if key and len(key.strip()) > 10:
                return f"✅ Streamlit secrets OK: {key[:8]}..."
            else:
                return "❌ Streamlit secrets key too short"
        else:
            return "❌ OPENAI_API_KEY not found in st.secrets"
    except Exception as e:
        return f"❌ Streamlit secrets error: {e}"