import json
import os
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, cast

import requests

from src.constants import DAEMON_DEFAULT_PORT
from src.exceptions import DaemonConnectionError
from src.settings import settings

IS_WINDOWS = os.name == "nt"


def runtime_filepath() -> str:
    return os.path.join(settings.app_data_root, settings.daemon.runtime_filename)


def read_runtime() -> Optional[Dict[str, Any]]:
    path = runtime_filepath()
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        pid = int(data.get("pid", 0))
        if pid and not _pid_alive(pid):
            # Stale descriptor from a crashed daemon.
            os.remove(path)
            return None
        return cast(Dict[str, Any], data)
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _pid_alive(pid: int) -> bool:
    if IS_WINDOWS:
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
        )
        return str(pid) in (out.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


class DaemonClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    @classmethod
    def connect(cls) -> "DaemonClient":
        rt = read_runtime()
        if not rt:
            raise DaemonConnectionError(
                "Daemon is not running. Start it with: gsc daemon start"
            )
        base = f"http://{rt.get('host', '127.0.0.1')}:{rt['port']}"
        client = cls(base)
        try:
            client.get("/health")
        except requests.RequestException:
            raise DaemonConnectionError(
                f"Daemon descriptor found at {base} but it does not answer. "
                f"Try: gsc daemon stop && gsc daemon start"
            )
        return client

    # ---- generic ---------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = self.base_url + path
        resp = requests.request(method, url, json=body, params=params, timeout=120)
        if resp.status_code >= 400:
            detail: Any = None
            try:
                detail = resp.json().get("detail")
            except ValueError:
                detail = resp.text[:300]
            raise RuntimeError(
                f"{method} {path} failed " f"({resp.status_code}): {detail}"
            )
        return cast(Dict[str, Any], resp.json())

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.request("GET", path, params=params)

    def post(self, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.request("POST", path, body=body)

    def delete(self, path: str) -> Dict[str, Any]:
        return self.request("DELETE", path)

    # ---- typed helpers -----------------------------------------------------

    def status(self) -> Dict[str, Any]:
        return self.get("/status")

    def list_games(self) -> List[Dict[str, Any]]:
        return cast(List[Dict[str, Any]], self.get("/games")["games"])

    def add_game(
        self,
        path: str,
        name: Optional[str] = None,
        auto_snapshot: bool = True,
    ) -> Dict[str, Any]:
        return self.post(
            "/games",
            {"path": path, "name": name, "auto_snapshot": auto_snapshot},
        )

    def remove_game(self, name_or_id: str) -> Dict[str, Any]:
        return self.delete(f"/games/{name_or_id}")

    def snapshot(
        self,
        name_or_id: str,
        message: Optional[str] = None,
        allow_empty: bool = False,
    ) -> Dict[str, Any]:
        return self.post(
            f"/games/{name_or_id}/snapshot",
            {"message": message, "allow_empty": allow_empty},
        )

    def snapshots(
        self,
        name_or_id: str,
        branch: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        return cast(
            List[Dict[str, Any]],
            self.get(
                f"/games/{name_or_id}/snapshots",
                params={"branch": branch, "limit": limit},
            )["snapshots"],
        )

    def restore(
        self, name_or_id: str, snapshot_id: str, hard: bool = False
    ) -> Dict[str, Any]:
        return self.post(
            f"/games/{name_or_id}/restore",
            {"snapshot_id": snapshot_id, "hard": hard},
        )

    def branches(self, name_or_id: str) -> Dict[str, Any]:
        return self.get(f"/games/{name_or_id}/branches")

    def create_branch(
        self,
        name_or_id: str,
        name: str,
        from_snapshot: Optional[str] = None,
        switch: bool = False,
    ) -> Dict[str, Any]:
        return self.post(
            f"/games/{name_or_id}/branches",
            {"name": name, "from_snapshot": from_snapshot, "switch": switch},
        )

    def switch_branch(self, name_or_id: str, branch: str) -> Dict[str, Any]:
        return self.post(f"/games/{name_or_id}/switch", {"branch": branch})


def start_daemon(port: Optional[int] = None, wait_seconds: int = 20) -> int:
    """Spawn the daemon detached; returns the port it listens on."""
    existing = read_runtime()
    if existing and port_open(existing["host"], existing["port"]):
        raise DaemonConnectionError(
            f"Daemon already running on port {existing['port']}"
        )
    port = port or DAEMON_DEFAULT_PORT
    log_path = os.path.join(settings.app_data_root, "daemon.log")
    os.makedirs(settings.app_data_root, exist_ok=True)
    kwargs = {}
    if IS_WINDOWS:
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    argv = [sys.executable, "-m", "src.daemon", "--port", str(port)]
    subprocess.Popen(  # type: ignore[call-overload]
        argv, stdout=open(log_path, "ab"), stderr=subprocess.STDOUT, **kwargs
    )
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if port_open("127.0.0.1", port, timeout=0.3):
            return port
        time.sleep(0.4)
    raise DaemonConnectionError(
        f"Daemon did not come up within {wait_seconds}s. " f"Check log: {log_path}"
    )


def stop_daemon(wait_seconds: int = 10) -> bool:
    """Returns True when the daemon confirmed shutdown."""
    rt = read_runtime()
    if not rt:
        return False
    try:
        requests.post(f"http://{rt['host']}:{rt['port']}/shutdown", timeout=5)
    except requests.RequestException:
        pass
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if not port_open(rt["host"], rt["port"], timeout=0.3):
            return True
        time.sleep(0.3)
    return False
