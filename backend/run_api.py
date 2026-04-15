#!/usr/bin/env python
"""
FastAPI server runner.

Supports:
- Development (hot reload)
- Production (multi-worker)
- Safe defaults
- Environment-driven configuration
"""

import os
import sys
import logging
from pathlib import Path

import uvicorn


# ------------------------------------------------------------------------------
# Path & environment setup (safe)
# ------------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Do NOT hardcode environment — allow override
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    os.getenv("DJANGO_SETTINGS_MODULE", "backend.config.dev"),
)


# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("run_api")


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run FastAPI server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload (dev only)"
    )
    parser.add_argument(
        "--workers", type=int, default=1, help="Number of worker processes"
    )
    parser.add_argument(
        "--log-level", default="info", choices=["debug", "info", "warning", "error"]
    )
    parser.add_argument("--access-log", action="store_true", help="Enable access log")

    args = parser.parse_args()

    # ------------------------------------------------------------------------------
    # Safety checks
    # ------------------------------------------------------------------------------

    if args.reload and args.workers > 1:
        logger.error("Reload mode does not support multiple workers")
        sys.exit(1)

    if args.workers < 1:
        logger.error("Workers must be >= 1")
        sys.exit(1)

    # ------------------------------------------------------------------------------
    # Environment awareness
    # ------------------------------------------------------------------------------

    is_dev = args.reload or os.getenv("ENV", "").lower() == "dev"

    logger.info(
        "Starting FastAPI server | env=%s | reload=%s | workers=%d",
        "development" if is_dev else "production",
        args.reload,
        args.workers,
    )

    # ------------------------------------------------------------------------------
    # Uvicorn configuration
    # ------------------------------------------------------------------------------

    logger.info("=" * 40)
    logger.info(f"Server running at http://{args.host}:{args.port}")
    logger.info(f"API Docs: http://{args.host}:{args.port}/api/docs")
    logger.info("=" * 40)

    config = uvicorn.Config(
        app="apps.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level=args.log_level,
        access_log=args.access_log,
        env_file=".env",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )

    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
