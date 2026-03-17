#!/usr/bin/env python
"""
Run script for Daphne ASGI server (production).
Runs both Django Channels and FastAPI on the same port.

Usage:
    python run_daphne.py                    # Run on default port 8000
    python run_daphne.py --port 8080         # Run on custom port
    python run_daphne.py --bind 0.0.0.0      # Bind to all interfaces
"""
#!/usr/bin/env python
import os
import sys
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    os.getenv("DJANGO_SETTINGS_MODULE", "backend.config.prod"),
)

def main():
    from daphne.server import Server
    from backend.asgi import app

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--bind")

    args = parser.parse_args()

    # endpoint = args.bind or f"{args.host}:{args.port}"
    endpoint = f"tcp:port={args.port}:interface={args.host}"


    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    )

    server = Server(
        app,
        [endpoint],
    )

    server.run()

if __name__ == "__main__":
    main()
