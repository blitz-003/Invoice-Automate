"""Start both servers for the invoice-intake demo in one command.

Usage:
    python scripts/start_services.py           # API on :8000, accounting mock on :8080
    python scripts/start_services.py --port 8123 --accounting 8080
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    args = sys.argv[1:]
    intake_port = 8000
    accounting_port = 8080
    i = 0
    while i < len(args):
        if args[i] == "--port":
            intake_port = int(args[i + 1]); i += 2
        elif args[i] == "--accounting":
            accounting_port = int(args[i + 1]); i += 2
        else:
            i += 1

    from app.config import get_settings

    settings = get_settings()
    print(f"Intake API  -> http://localhost:{intake_port}   (/docs, /ui, /health)")
    print(f"Accounting  -> http://localhost:{accounting_port}   (mock, used by AccountingClient)")

    # Run the accounting mock as a background uvicorn server.
    import app.api.accounting_api as accounting_api

    mock_cfg = uvicorn.Config(accounting_api.app, host="127.0.0.1",
                              port=accounting_port, log_level="info")
    mock_server = uvicorn.Server(mock_cfg)
    threading.Thread(target=mock_server.run, daemon=True).start()

    settings.ensure_dirs()
    import app.main as main_app

    cfg = uvicorn.Config(main_app.app, host="127.0.0.1", port=intake_port, log_level="info")
    # Importing main app after the mock is booting so lifespan dirs exist.
    time.sleep(0.3)
    uvicorn.Server(cfg).run()


if __name__ == "__main__":
    main()