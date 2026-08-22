"""
Daemon entry point.

Usage: python -m src.daemon [--port N]

Starts the FastAPI server on 127.0.0.1, writes a runtime descriptor
(pid + port) into the app data root so the CLI can locate the daemon,
and cleans the descriptor up on exit.
"""

import argparse
import atexit
import json
import os
import sys

import uvicorn

from src.api.server import create_app
from src.api.state import AppState
from src.constants import DAEMON_HOST
from src.core.controller import DirectoryController
from src.core.snapshot_service import SnapshotService
from src.logger import LoggerFactory
from src.models.metadata import Metadata
from src.settings import settings
from src.utils import find_port

logger = LoggerFactory.getLogger(__name__)


def runtime_filepath() -> str:
    return os.path.join(
        settings.app_data_root, settings.daemon.runtime_filename
    )


def write_runtime_file(port: int) -> None:
    os.makedirs(settings.app_data_root, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "port": port,
        "host": settings.daemon.host,
    }
    tmp = runtime_filepath() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.replace(tmp, runtime_filepath())
    logger.info(f"Runtime descriptor written: {runtime_filepath()}")


def remove_runtime_file() -> None:
    try:
        if os.path.exists(runtime_filepath()):
            os.remove(runtime_filepath())
    except OSError as ex:
        logger.warning(f"Could not remove runtime file: {ex}")


def build_app():
    metadata = Metadata.load(path=settings.metadata.filepath)
    service = SnapshotService(
        repos_root=settings.vault.repos_path,
        quiet_period_sec=settings.save_state.quiet_period_sec,
        cooldown_sec=settings.save_state.save_cooldown_sec,
        limit_intervals=settings.save_state.limit_save_intervals,
        game_resolver=metadata.find_game,
    )
    controller = DirectoryController(
        metadata=metadata, snapshot_service=service
    )
    controller.start_all()
    state = AppState(metadata=metadata, controller=controller, service=service)
    return create_app(state), controller


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="gamesave-cloud daemon")
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=settings.daemon.port,
        help=f"Port to listen on (default {settings.daemon.port})",
    )
    args = parser.parse_args(argv)

    try:
        port = find_port(port=args.port, max_port=65535)
    except Exception:
        logger.error("No available port found")
        sys.exit(1)

    app, controller = build_app()
    write_runtime_file(port)
    atexit.register(remove_runtime_file)

    logger.info(f"gamesave-cloud daemon listening on {DAEMON_HOST}:{port}")
    try:
        uvicorn.run(app, host=DAEMON_HOST, port=port, log_level="warning")
    finally:
        remove_runtime_file()


if __name__ == "__main__":
    main()
