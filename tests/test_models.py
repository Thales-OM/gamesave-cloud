"""Tests for GameEntry, Metadata and SnapshotInfo models."""

from pathlib import Path

import pytest

from src.exceptions import MetadataError
from src.models.game import GameEntry
from src.models.metadata import Metadata
from src.models.remote_config import RemoteConfig


class TestGameEntry:
    def test_slug_deterministic_from_name(self, tmp_path: Path) -> None:
        d1 = tmp_path / "a"
        d2 = tmp_path / "b"
        d1.mkdir()
        d2.mkdir()
        a = GameEntry(name="Half-Life 2", path=d1)
        b = GameEntry(name="half-life 2", path=d2)
        assert a.slug == b.slug

    def test_slug_sanitizes(self, tmp_path: Path) -> None:
        d = tmp_path / "x"
        d.mkdir()
        g = GameEntry(name="Dark Souls: PTDE!", path=d)
        assert " " not in g.slug
        assert ":" not in g.slug
        assert g.slug == g.slug.lower()

    def test_default_branch_and_engine(self, tmp_path: Path) -> None:
        d = tmp_path / "y"
        d.mkdir()
        g = GameEntry(name="X", path=d)
        assert g.default_branch == "main"
        assert g.engine_type == "git"
        assert g.auto_snapshot is True


class TestMetadata:
    def test_add_and_find_game(self, tmp_path: Path, save_dir: Path) -> None:
        md = Metadata.load(path=str(tmp_path / "md.json"))
        game = GameEntry(name="My Game", path=save_dir)
        md.add_game(game)
        assert md.find_game(game.slug) is game
        assert md.find_game("my game") is game
        assert md.find_game(game.id) is game
        assert md.find_game("my") is game  # partial match

    def test_duplicate_rejected(self, metadata: Metadata, save_dir: Path) -> None:
        with pytest.raises(MetadataError):
            metadata.add_game(GameEntry(name="My Game", path=save_dir))

    def test_find_missing_returns_none(self, metadata: Metadata) -> None:
        assert metadata.find_game("nope") is None

    def test_roundtrip_persists_games(self, tmp_path: Path, save_dir: Path) -> None:
        path = tmp_path / "md.json"
        md = Metadata.load(path=str(path))
        md.add_game(GameEntry(name="Round Trip", path=save_dir))
        md.save()
        md2 = Metadata.load(path=str(path))
        assert len(md2.games) == 1
        assert md2.games[0].name == "Round Trip"

    def test_remotes_crud(self, tmp_path: Path) -> None:
        md = Metadata.load(path=str(tmp_path / "md.json"))
        r = RemoteConfig(name="usb", type="filesystem", options={"path": "D:/backups"})
        md.add_remote(r)
        assert md.find_remote("usb") is r
        md.remove_remote(r.id)
        assert len(md.remotes) == 0
