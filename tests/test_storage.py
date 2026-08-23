"""Tests for storage backends and SyncService push/pull."""

import json
from pathlib import Path
from typing import Tuple, cast

import pytest

from src.core.snapshot_service import SnapshotService
from src.core.sync_service import SyncService
from src.exceptions import MetadataError, StorageNotRegisteredError
from src.models.game import GameEntry
from src.models.metadata import Metadata
from src.models.remote_config import RemoteConfig
from src.storage.base import get_storage_class
from src.storage.bundle import BundleStorage
from tests.conftest import seed

TwoMachines = Tuple[SyncService, SyncService, GameEntry, GameEntry, Path, Path]


class TestRegistry:
    def test_builtin_types_registered(self) -> None:
        for t in ("filesystem", "s3", "webdav", "yandex"):
            assert get_storage_class(t).TYPE == t

    def test_unknown_type_raises(self) -> None:
        with pytest.raises(StorageNotRegisteredError):
            get_storage_class("gdrive")


class TestFilesystemStorage:
    def test_fields(self) -> None:
        cls = get_storage_class("filesystem")
        names = {f.name for f in cls.fields()}
        assert "path" in names

    def test_push_pull_artifacts(
        self, vault: Path, game: GameEntry, tmp_path: Path
    ) -> None:
        dest = tmp_path / "usb"
        svc = SnapshotService(repos_root=str(vault), game_resolver=lambda x: game)
        engine = svc.engine_for(game)
        seed(game.path, "slot1.sav", "v1")
        engine.snapshot("one")

        cfg = RemoteConfig(name="usb", type="filesystem", options={"path": str(dest)})
        store = cast(BundleStorage, get_storage_class("filesystem")(cfg, game))
        store.sync_push(engine)
        files = [p.name for p in dest.rglob("*") if p.is_file()]
        assert any(f.endswith(".bundle") for f in files)
        assert any(f.endswith(".json") for f in files)

        # machine B pulls into a fresh worktree
        saves_b = tmp_path / "saves-b"
        saves_b.mkdir()
        g2 = GameEntry(name="My Game", path=saves_b)
        e2 = SnapshotService(
            repos_root=str(tmp_path / "vault-b"), game_resolver=lambda x: g2
        ).engine_for(g2)
        _, changed = store.sync_pull(e2)
        assert changed in (True, False)
        assert (saves_b / "slot1.sav").read_text() == "v1"

    def test_latest_pointer_content(
        self, vault: Path, game: GameEntry, tmp_path: Path
    ) -> None:
        dest = tmp_path / "usb"
        svc = SnapshotService(repos_root=str(vault), game_resolver=lambda x: game)
        engine = svc.engine_for(game)
        engine.snapshot("one")
        cfg = RemoteConfig(
            name="usb",
            type="filesystem",
            options={"path": str(dest), "prefix": "b"},
        )
        store = cast(BundleStorage, get_storage_class("filesystem")(cfg, game))
        name = store.sync_push(engine)
        pointer_path = dest / "b" / game.slug / "latest.json"
        pointer = json.loads(pointer_path.read_text())
        assert pointer["artifact"] == name
        assert pointer["game"] == game.name


class TestSyncService:
    @pytest.fixture
    def two_machines(self, tmp_path: Path, save_dir: Path) -> TwoMachines:
        """Machine A tracks save_dir; machine B has an empty folder."""
        md_a = Metadata.load(path=str(tmp_path / "a.json"))
        md_b = Metadata.load(path=str(tmp_path / "b.json"))
        dest = tmp_path / "usb"

        ga = GameEntry(name="CloudGame", path=save_dir)
        md_a.add_game(ga)
        ra = RemoteConfig(name="usb", type="filesystem", options={"path": str(dest)})
        md_a.add_remote(ra)
        ga.remote_id = ra.id

        saves_b = tmp_path / "saves-b"
        saves_b.mkdir()
        gb = GameEntry(name="CloudGame", path=saves_b)
        md_b.add_game(gb)
        rb = RemoteConfig(name="usb", type="filesystem", options={"path": str(dest)})
        md_b.add_remote(rb)
        gb.remote_id = rb.id

        sa = SnapshotService(repos_root=str(tmp_path / "vault-a"))
        sb = SnapshotService(repos_root=str(tmp_path / "vault-b"))
        sync_a = SyncService(metadata=md_a, engine_resolver=sa.engine_for)
        sync_b = SyncService(metadata=md_b, engine_resolver=sb.engine_for)
        return sync_a, sync_b, ga, gb, save_dir, saves_b

    def test_push_pull_flow(self, two_machines: TwoMachines) -> None:
        sync_a, sync_b, ga, gb, save_dir, saves_b = two_machines
        seed(save_dir, "save.dat", "cloud-v1")
        sync_a.push_game(ga)

        sync_b.pull_game(gb)
        assert (saves_b / "save.dat").read_text() == "cloud-v1"

    def test_second_pull_fast_forwards(self, two_machines: TwoMachines) -> None:
        sync_a, sync_b, ga, gb, save_dir, saves_b = two_machines
        seed(save_dir, "save.dat", "v1")
        sync_a.push_game(ga)
        sync_b.pull_game(gb)
        seed(save_dir, "save.dat", "v2")
        sync_a.push_game(ga)
        sync_b.pull_game(gb)
        assert (saves_b / "save.dat").read_text() == "v2"

    def test_push_without_remote_raises(self, tmp_path: Path, save_dir: Path) -> None:
        md = Metadata.load(path=str(tmp_path / "m.json"))
        g = GameEntry(name="NoRemote", path=save_dir)
        md.add_game(g)
        svc = SnapshotService(repos_root=str(tmp_path / "r"))
        sync = SyncService(metadata=md, engine_resolver=svc.engine_for)
        with pytest.raises(MetadataError):
            sync.push_game(g)
