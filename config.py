"""Central place for every setting in the project.

Why one config file?
    If a number (like the chunk size) or a secret (like the API key) is needed
    in many places, we define it ONCE here and import it everywhere else.
    That keeps the rest of the code clean and easy to change.

Secrets:
    The API key is read from an environment variable (or from a local ".env"
    file). It is never written in the source code and never shown in the UI.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv not installed: real environment variables still work
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent.parent

# Load variables from the ".env" file (if it exists) into the environment.
if load_dotenv is not None:
    load_dotenv(BASE_DIR / ".env")


def _int_env(name: str, default: int) -> int:
    """Read a positive integer from the environment, or fall back to `default`."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


# ---------------------------------------------------------------- app / storage
APP_NAME = "AI Study Assistant"
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.getenv("STUDY_DB_PATH") or DATA_DIR / "study_assistant.db")

# ---------------------------------------------------------------- PDF handling
MAX_UPLOAD_MB = _int_env("MAX_UPLOAD_MB", 25)
MAX_PAGES = _int_env("MAX_PAGES", 500)
# A page with fewer characters than this is treated as "no readable text"
# (usually a scanned image page).
MIN_TEXT_CHARS_PER_PAGE = 20

# ---------------------------------------------------------------- chunking / retrieval
CHUNK_SIZE = _int_env("CHUNK_SIZE", 900)        # max characters per chunk
CHUNK_OVERLAP = _int_env("CHUNK_OVERLAP", 150)  # characters shared between neighbours
TOP_K = _int_env("TOP_K", 4)                    # how many chunks to retrieve per question

# ---------------------------------------------------------------- LLM (Anthropic Claude)
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5-5")
LLM_MAX_TOKENS = _int_env("LLM_MAX_TOKENS", 2000)
LLM_TIMEOUT_SECONDS = 60
LLM_MAX_RETRIES = 2

_PLACEHOLDER_KEYS = {"", "your-api-key-here", "changeme", "your_api_key_here"}


def get_api_key() -> str | None:
    """Return the API key, or None if it is missing or still the placeholder."""
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    return None if key.lower() in _PLACEHOLDER_KEYS else key


def api_key_available() -> bool:
    """True when a usable API key has been configured."""
    return get_api_key() is not None
