import os
import tempfile
from pathlib import Path

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="invoice-intake-tests-"))
_TEST_ROOT.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("STORAGE_ROOT", str(_TEST_ROOT / "data"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_ROOT / 'invoice.db'}")
os.environ.setdefault("WE_WH_DIR", str(_TEST_ROOT / "we_wh"))
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("GROQ_BASE_URL", "http://127.0.0.1:1/v1")


import pytest


@pytest.fixture(autouse=True)
def _reset_settings():
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def schema():
    from app.schema.fast_rules import load_schema

    return load_schema()