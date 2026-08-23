from typing import Any, Dict, List

import requests
from requests import Response

from src.exceptions import (
    StorageAuthError,
    StorageConnectionError,
    StorageError,
)
from src.models.game import GameEntry
from src.models.remote_config import CredentialField, RemoteConfig
from src.storage.base import register_storage
from src.storage.bundle import BundleStorage

API_BASE = "https://cloud-api.yandex.net/v1/disk"


@register_storage("yandex")
class YandexDiskStorage(BundleStorage):
    """
    Yandex Disk via its native REST API (OAuth token).

    Options:
      prefix  (optional) folder on the disk, e.g. gamesave-cloud
    Secrets:
      token  OAuth token from https://oauth.yandex.ru
    """

    FIELDS = (
        CredentialField(
            name="prefix",
            prompt="Folder on Yandex Disk (default: apps/gamesave-cloud)",
            required=False,
        ),
        CredentialField(
            name="token",
            prompt="Yandex OAuth token",
            secret=True,
        ),
    )

    def __init__(self, config: RemoteConfig, game: GameEntry):
        super().__init__(config=config, game=game)
        self.prefix = self._normalize_prefix(
            self.option("prefix", "apps/gamesave-cloud")
        )

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"OAuth {self.secret('token')}"}

    def _api(self, method: str, path: str, **kwargs: Any) -> Response:
        try:
            return requests.request(
                method,
                API_BASE + path,
                headers=self._headers(),
                timeout=60,
                **kwargs,
            )
        except requests.RequestException as ex:
            raise StorageConnectionError(f"Yandex.Disk error: {ex}") from ex

    @staticmethod
    def _check(resp: Response, action: str) -> None:
        if resp.status_code == 401:
            raise StorageAuthError("Yandex.Disk rejected the OAuth token")
        if resp.status_code >= 300:
            detail = ""
            try:
                detail = resp.json().get("message", "")
            except ValueError:
                pass
            raise StorageError(
                f"Yandex.Disk {action} failed " f"(HTTP {resp.status_code}): {detail}"
            )

    def test_connection(self) -> None:
        resp = self._api("GET", "/")
        self._check(resp, "probe")

    def push(self, artifact_path: str, remote_name: str) -> None:
        full = f"{self._disk_path(remote_name)}"
        # ensure parent folders exist
        parts = full.strip("/").split("/")[:-1]
        for i in range(len(parts)):
            folder = "/" + "/".join(parts[: i + 1])
            self._api("PUT", "/resources", params={"path": folder})
        resp = self._api(
            "GET",
            "/resources/upload",
            params={"path": full, "overwrite": "true"},
        )
        self._check(resp, "upload-url")
        href = resp.json().get("href")
        with open(artifact_path, "rb") as data:
            try:
                put = requests.put(href, data=data, timeout=600)
            except requests.RequestException as ex:
                raise StorageConnectionError(f"Yandex.Disk upload error: {ex}") from ex
        if put.status_code >= 300:
            raise StorageError(f"Yandex.Disk upload failed: HTTP {put.status_code}")

    def pull(self, remote_name: str, local_path: str) -> None:
        full = self._disk_path(remote_name)
        resp = self._api("GET", "/resources/download", params={"path": full})
        if resp.status_code == 404:
            raise StorageError(f"Not found on Yandex.Disk: {remote_name}")
        self._check(resp, "download-url")
        href = resp.json().get("href")
        try:
            get = requests.get(href, stream=True, timeout=600)
        except requests.RequestException as ex:
            raise StorageConnectionError(f"Yandex.Disk download error: {ex}") from ex
        if get.status_code >= 300:
            raise StorageError(f"Yandex.Disk download failed: HTTP {get.status_code}")
        with open(local_path, "wb") as f:
            for chunk in get.iter_content(1024 * 512):
                f.write(chunk)

    def list_artifacts(self, prefix: str = "") -> List[str]:
        base = prefix or self._base()
        folder = self._disk_path(base)
        resp = self._api(
            "GET",
            "/resources",
            params={"path": folder, "limit": "1000"},
        )
        if resp.status_code == 404:
            return []
        self._check(resp, "listing")
        items = resp.json().get("_embedded", {}).get("items", [])
        return sorted(
            f"{base}/{item['name']}"
            for item in items
            if item.get("file") and item["name"].endswith(".bundle")
        )

    def _disk_path(self, remote_name: str) -> str:
        return f"/{self.prefix}/{remote_name}"
