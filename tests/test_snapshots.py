"""Tests for SnapshotService debouncing/cooldown and the controller."""

import time
from pathlib import Path
from typing import List, Tuple

import pytest

from src.core.controller import DirectoryController
from src.core.snapshot_service import SnapshotService
from src.exceptions import GameNotFoundError
from src.models.game import GameEntry
from src.models.metadata import Metadata
from src.models.snapshot_info import SnapshotInfo
from tests.conftest import seed


@pytest.fixture
def service(vault: Path, metadata: Metadata, game: GameEntry) -> SnapshotService:
    return SnapshotService(
        repos_root=str(vault),
        quiet_period_sec=1,
        cooldown_sec=4,
        limit_intervals=True,
        game_resolver=metadata.find_game,
    )


class TestSnapshotService:
    def test_debounce_coalesces(
        self, service: SnapshotService, save_dir: Path, game: GameEntry
    ) -> None:
        seed(save_dir, "a.sav", "1")
        service.mark_active(game)
        time.sleep(0.2)
        seed(save_dir, "b.sav", "2")
        service.mark_active(game)
        time.sleep(3.5)
        snaps = service.engine_for(game).list_snapshots()
        assert len(snaps) == 1  # two events -> one snapshot

    def test_cooldown_blocks(
        self, service: SnapshotService, save_dir: Path, game: GameEntry
    ) -> None:
        seed(save_dir, "a.sav", "1")
        service.mark_active(game)
        time.sleep(3.0)  # first auto snapshot lands (~quiet 1s)
        snaps = service.engine_for(game).list_snapshots()
        assert len(snaps) == 1
        # second burst inside cooldown window must be suppressed
        seed(save_dir, "b.sav", "2")
        service.mark_active(game)
        time.sleep(2.0)
        snaps = service.engine_for(game).list_snapshots()
        assert len(snaps) == 1

    def test_snapshot_now_bypasses(
        self, service: SnapshotService, save_dir: Path, game: GameEntry
    ) -> None:
        info = service.snapshot_now(game, message="manual")
        assert info is not None
        assert info.message == "manual"

    def test_on_snapshotted_hook(
        self, service: SnapshotService, game: GameEntry, save_dir: Path
    ) -> None:
        calls: List[Tuple[str, str]] = []

        def hook(g: GameEntry, s: SnapshotInfo) -> None:
            calls.append((g.id, s.id))

        service._on_snapshotted = hook
        service.snapshot_now(game, message="hooked")
        assert len(calls) == 1


class TestController:
    def test_add_remove_lifecycle(
        self, vault: Path, metadata: Metadata, tmp_path: Path
    ) -> None:
        svc = SnapshotService(repos_root=str(vault), game_resolver=metadata.find_game)
        ctl = DirectoryController(metadata, svc)
        folder = tmp_path / "fresh-game"
        folder.mkdir()
        added = ctl.add_game(path=folder, name=None, auto_snapshot=True)
        assert added.name == "fresh-game"
        assert ctl.get_game(added.id).name == "fresh-game"
        removed = ctl.remove_game(added.id)
        assert removed.name == "fresh-game"
        with pytest.raises(GameNotFoundError):
            ctl.get_game(added.id)

    def test_status_string(self, vault: Path, metadata: Metadata) -> None:
        svc = SnapshotService(repos_root=str(vault), game_resolver=metadata.find_game)
        ctl = DirectoryController(metadata, svc)
        assert ctl.status == "initialized"
        ctl.start_all()
        assert ctl.status == "started"
        ctl.stop_all()
        assert ctl.status == "stopped"
