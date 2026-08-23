"""API-level tests using FastAPI TestClient."""

import pytest
from fastapi.testclient import TestClient

from src.api.server import create_app
from src.api.state import AppState
from src.core.controller import DirectoryController
from src.core.snapshot_service import SnapshotService
from src.models.metadata import Metadata


@pytest.fixture
def client(tmp_path, save_dir):
    metadata = Metadata.load(path=tmp_path / "md.json")
    service = SnapshotService(
        repos_root=tmp_path / "repos",
        quiet_period_sec=1,
        cooldown_sec=0,
        limit_intervals=True,
        game_resolver=metadata.find_game,
    )
    controller = DirectoryController(metadata, service)
    state = AppState(
        metadata=metadata,
        controller=controller,
        service=service,
        sync=None,  # type: ignore
    )
    return TestClient(create_app(state))


class TestHealthAndGames:
    def test_health(self, client):
        assert client.get("/health").json()["status"] == "ok"

    def test_status(self, client):
        data = client.get("/status").json()
        assert "games" in data and "remotes" in data

    def test_add_list_remove_game(self, client, save_dir):
        r = client.post("/games", json={"path": str(save_dir)})
        assert r.status_code == 200
        game = r.json()["game"]

        games = client.get("/games").json()["games"]
        assert [g["id"] for g in games] == [game["id"]]

        r = client.delete(f"/games/{game['id']}")
        assert r.status_code == 200
        assert client.get("/games").json()["games"] == []

    def test_duplicate_add_conflict(self, client, save_dir):
        body = {"path": str(save_dir)}
        client.post("/games", json=body)
        assert client.post("/games", json=body).status_code == 409


class TestSnapshotEndpoints:
    @pytest.fixture
    def game(self, client, save_dir):
        r = client.post("/games", json={"path": str(save_dir)}).json()
        return r["game"]

    def test_snapshot_and_log(self, client, save_dir, game):
        (save_dir / "slot1.sav").write_text("changed")
        r = client.post(
            f"/games/{game['id']}/snapshot",
            json={"message": "via api"},
        )
        assert r.json()["snapshot"]["message"] == "via api"

        snaps = client.get(f"/games/{game['id']}/snapshots").json()[
            "snapshots"
        ]
        assert len(snaps) == 1

    def test_restore(self, client, save_dir, game):
        client.post(f"/games/{game['id']}/snapshot", json={"message": "first"})
        snaps = client.get(f"/games/{game['id']}/snapshots").json()[
            "snapshots"
        ]
        (save_dir / "slot1.sav").write_text("mutated")
        sid = snaps[0]["id"]
        r = client.post(
            f"/games/{game['id']}/restore", json={"snapshot_id": sid}
        )
        assert r.status_code == 200
        assert (save_dir / "slot1.sav").read_text() == "v1"


class TestRemotesApi:
    def test_remote_crud(self, client):
        r = client.post(
            "/remotes",
            json={
                "name": "usb",
                "type": "filesystem",
                "options": {"path": "D:/backups"},
            },
        )
        assert r.status_code == 200
        remote_id = r.json()["id"]

        listed = client.get("/remotes").json()["remotes"]
        assert listed[0]["name"] == "usb"

        r = client.delete(f"/remotes/{remote_id}")
        assert r.status_code == 200
        assert client.get("/remotes").json()["remotes"] == []

    def test_unknown_type_rejected(self, client):
        r = client.post(
            "/remotes",
            json={
                "name": "x",
                "type": "carrier-pigeon",
                "options": {},
            },
        )
        assert r.status_code in (400, 422)


class TestDetectEndpoint:
    def test_detect_shape(self, client, monkeypatch):
        from src.detection.base import DetectedGame
        from src.detection.registry import _PROVIDERS

        class Stub:
            name = "stub"

            def find_games(self):
                return [
                    DetectedGame(
                        name="StubGame",
                        path="C:/s",  # type: ignore
                        source="stub",
                    ),
                ]

        saved = list(_PROVIDERS)
        _PROVIDERS.clear()
        _PROVIDERS.append(Stub())
        try:
            data = client.get("/detect").json()
            assert data["games"][0]["name"] == "StubGame"
            data = client.get("/detect?source=steam").json()
            assert data["games"] == []
        finally:
            _PROVIDERS.clear()
            _PROVIDERS.extend(saved)
