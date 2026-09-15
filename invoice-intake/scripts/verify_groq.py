"""Verify that the configured Groq model IDs actually resolve.

Usage:
    python scripts/verify_groq.py                 # use .env settings
    python scripts/verify_groq.py llama-3.3-70b-versatile qwen/qwen3.8-27b

Exit codes:
    0  all configured models were found (or GROQ_API_KEY is not set)
    1  a configured/inspect model id could not be resolved
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.clients.llm_client import LLMClient
from app.config import get_settings


def main() -> int:
    settings = get_settings()
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    candidates = args or [settings.text_llm_model, settings.vision_llm_model]

    if not settings.groq_api_key:
        print("GROQ_API_KEY is not set - skipping model verification.")
        return 0

    print(f"Checking Groq ({settings.groq_base_url}) for: {candidates}")
    available = LLMClient().list_models()
    if not available:
        print("Could not reach the Groq model list endpoint.")
        return 1

    ok = True
    for model in candidates:
        match = next((m for m in available if m == model or model in m), None)
        if match is not None:
            print(f"  [ok]     {model}")
        else:
            print(f"  [MISS]   {model}")
            ok = False

    if not ok:
        print("Configured model ids that could not be found. Update config.py / .env with:")
        for m in sorted(available):
            print(f"    - {m}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())