"""Tests for the GitEngine snapshot/branch/restore lifecycle."""

from pathlib import Path
from typing import cast

import pytest

from src.core.engine.git_engine import GitEngine
from src.exceptions import BranchError, SnapshotNotFoundError
from src.models.game import GameEntry
from src.models.snapshot_info import SnapshotInfo
from tests.conftest import seed


class TestSnapshots:
    def test_snapshot_and_list(self, engine: GitEngine, save_dir: Path) -> None:
        info = cast(SnapshotInfo, engine.snapshot("first"))
        assert info.branch == "main"
        snaps = engine.list_snapshots()
        assert [s.id for s in snaps] == [info.id]

    def test_empty_snapshot_skipped(self, engine: GitEngine, save_dir: Path) -> None:
        seed(save_dir, "slot1.sav", "v2")
        engine.snapshot("real change")
        assert engine.snapshot("nothing") is None
        assert engine.snapshot("forced", allow_empty=True) is not None

    def test_restore_content(self, engine: GitEngine, save_dir: Path) -> None:
        s1 = cast(SnapshotInfo, engine.snapshot("one"))
        seed(save_dir, "slot1.sav", "v2")
        engine.snapshot("two")
        engine.restore(s1.id)
        assert (save_dir / "slot1.sav").read_text() == "v1"

    def test_restore_hard_moves_branch(self, engine: GitEngine, save_dir: Path) -> None:
        s1 = cast(SnapshotInfo, engine.snapshot("one"))
        seed(save_dir, "slot1.sav", "v2")
        engine.snapshot("two")
        engine.restore(s1.id, hard=True)
        head = engine.list_snapshots(limit=1)[0]
        assert head.id == s1.id
        assert (save_dir / "slot1.sav").read_text() == "v1"

    def test_missing_snapshot_raises(self, engine: GitEngine) -> None:
        with pytest.raises(SnapshotNotFoundError):
            engine.restore("deadbeef" * 5)


class TestBranches:
    def test_create_switch(self, engine: GitEngine, save_dir: Path) -> None:
        seed(save_dir, "slot1.sav", "base")
        base = engine.snapshot("base")
        assert base is not None
        engine.create_branch("exp", from_snapshot=base.id)
        engine.switch_branch("exp")
        assert engine.current_branch() == "exp"
        seed(save_dir, "experiment.sav", "x")
        exp_snap = cast(SnapshotInfo, engine.snapshot("on exp"))
        assert exp_snap.branch == "exp"

    def test_switch_back_restores_files(
        self, engine: GitEngine, save_dir: Path
    ) -> None:
        seed(save_dir, "slot1.sav", "base")
        engine.snapshot("base")
        engine.create_branch("side")
        engine.switch_branch("side")
        seed(save_dir, "only-side.sav", "x")
        engine.snapshot("side work")
        engine.switch_branch("main")
        assert not (save_dir / "only-side.sav").exists()
        assert (save_dir / "slot1.sav").read_text() == "base"

    def test_duplicate_branch_rejected(self, engine: GitEngine, save_dir: Path) -> None:
        seed(save_dir, "slot1.sav", "x")
        engine.snapshot("init")
        with pytest.raises(BranchError):
            engine.create_branch("main")


class TestBundleTransport:
    def test_export_import_roundtrip(
        self,
        engine: GitEngine,
        vault: Path,
        game: GameEntry,
        tmp_path: Path,
        save_dir: Path,
    ) -> None:
        seed(save_dir, "slot1.sav", "gen1")
        first = cast(SnapshotInfo, engine.snapshot("gen1"))
        bundle = str(tmp_path / "hist.bundle")
        engine.export_history(bundle)

        # machine B: fresh empty worktree + own repo dir
        other_saves = save_dir.parent / "machine-b"
        other_saves.mkdir(parents=True, exist_ok=True)
        g2 = game.model_copy(update={"path": other_saves})
        e2 = GitEngine(game=g2, repos_root=str(vault.parent / "vault-b"))
        e2.import_history(bundle)

        heads = {s.id for s in e2.list_snapshots()}
        assert first.id in heads
