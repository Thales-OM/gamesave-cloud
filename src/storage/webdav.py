from typing import Any, List, Optional, Tuple

from requests import request, Response, RequestException
from requests.utils import unquote  # type: ignore

from src.exceptions import (
    StorageConnectionError,
    StorageError,
)
from src.models.game import GameEntry
from src.models.remote_config import CredentialField, RemoteConfig
from src.storage.base import register_storage
from src.storage.bundle import BundleStorage


@register_storage("webdav")
class WebDAVStorage(BundleStorage):
    """
    Generic WebDAV server: many NAS boxes (Synology/QNAP), Nextcloud,
    ownCloud, etc.

    Options:
      url     (required) base WebDAV URL, e.g. https://nas.local:5006
      prefix  (optional) collection path inside it
    Secrets:
      username / password (stored in the OS keyring)
    """

    FIELDS = (
        CredentialField(name="url", prompt="WebDAV base URL"),
        CredentialField(
            name="prefix", prompt="Path on server (optional)", required=False
        ),
        CredentialField(name="username", prompt="Username", secret=True),
        CredentialField(name="password", prompt="Password", secret=True),
    )

    def __init__(self, config: RemoteConfig, game: GameEntry):
        super().__init__(config=config, game=game)
        self.base_url = str(self.option("url", "")).rstrip("/")
        if not self.base_url:
            raise StorageError("webdav storage requires 'url' option")

    def _url(self, remote_name: str) -> str:
        return f"{self.base_url}/{remote_name}"

    def _auth(self) -> Optional[Tuple[str, str]]:
        user = self.secret("username")
        password = self.secret("password")
        return (user, password) if user else None

    def _request(self, method: str, url: str, **kwargs: Any) -> Response:
        try:
            return request(method, url, auth=self._auth(), timeout=60, **kwargs)
        except RequestException as ex:
            raise StorageConnectionError(f"WebDAV error: {ex}") from ex

    @staticmethod
    def _check(resp: Response, action: str) -> None:
        if resp.status_code >= 300:
            raise StorageError(f"WebDAV {action} failed: HTTP {resp.status_code}")

    def _mkdirs(self, remote_name: str) -> None:
        """Create every missing collection along the artifact path."""
        parts = remote_name.split("/")[:-1]
        current = ""
        for part in parts:
            parent = current
            current = f"{current}/{part}".strip("/")
            resp = self._request(
                "MKCOL",
                f"{self.base_url}/{current}",
            )
            if resp.status_code not in (200, 201, 301, 405):
                # 405 = already exists; tolerate intermediate failures
                if resp.status_code == 409 and parent is not None:
                    continue
                self._check(resp, "MKCOL")

    def test_connection(self) -> None:
        resp = self._request("PROPFIND", self.base_url + "/", headers={"Depth": "0"})
        if resp.status_code in (207, 200):
            return
        if resp.status_code == 401:
            from src.exceptions import StorageAuthError

            raise StorageAuthError("WebDAV rejected the credentials")
        raise StorageConnectionError(f"WebDAV probe failed: HTTP {resp.status_code}")

    def push(self, artifact_path: str, remote_name: str) -> None:
        self._mkdirs(remote_name)
        with open(artifact_path, "rb") as data:
            resp = self._request("PUT", self._url(remote_name), data=data)
        self._check(resp, "upload")

    def pull(self, remote_name: str, local_path: str) -> None:
        resp = self._request("GET", self._url(remote_name), stream=True)
        if resp.status_code == 404:
            raise StorageError(f"Not found on remote: {remote_name}")
        self._check(resp, "download")
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(1024 * 512):
                f.write(chunk)

    def list_artifacts(self, prefix: str = "") -> List[str]:
        base = prefix or self._base()
        import re

        resp = self._request(
            "PROPFIND",
            self._url(base),
            headers={"Depth": "1"},
        )
        if resp.status_code == 404:
            return []
        self._check(resp, "PROPFIND")
        names = set()
        for href in re.findall(
            r"<D?:?href>([^<]+)</D?:?href>", resp.text, re.IGNORECASE
        ):
            path = href.split("//")[-1].split("/", 1)[-1]
            path = unquote(path)
            if path.endswith(".bundle"):
                names.add(path)
        return sorted(names - {""})
