"""Tests for detection providers and the VDF parser."""

import json

import pytest

from src.detection.base import DetectedGame
from src.detection.vdf import parse_vdf


class TestVdf:
    def test_simple(self):
        data = parse_vdf('"root"\n{\n"a"\t"1"\n"b" "2"\n}\n')
        assert data["root"]["a"] == "1"
        assert data["root"]["b"] == "2"

    def test_nested(self):
        data = parse_vdf('"outer"{\n"inner"{\n"k" "v"\n}\n}')
        assert data["outer"]["inner"]["k"] == "v"

    def test_windows_paths(self):
        text = '"LibraryFolders"{\n"path" "C:\\Games\\Steam"\n}'
        assert parse_vdf(text)["LibraryFolders"]["path"] == (
            "C:\\Games\\Steam"
        )


class TestSteamProvider:
    @pytest.fixture
    def fake_steam(self, tmp_path):
        steamapps = tmp_path / "steamapps"
        common = steamapps / "common"
        game = common / "Test Game Alpha"
        (game / "saves").mkdir(parents=True)
        exe = game / "bin"
        exe.mkdir()
        (exe / "alpha.exe").write_text("x")
        (game / "saves" / "slot1.sav").write_text("x")
        (steamapps / "libraryfolders.vdf").write_text(
            f'"LibraryFolders"\n{{\n"1"\t"{tmp_path}"\n}}\n'
        )
        (steamapps / "appmanifest_480.acf").write_text(
            '"AppState"\n{\n'
            ' "appid"  "480"\n'
            ' "name"   "test_game_alpha"\n'
            ' "installdir" "Test Game Alpha"\n'
            "}\n"
        )
        return tmp_path

    def test_find_games(self, fake_steam):
        from src.detection.steam import SteamProvider

        sp = SteamProvider()
        games = sp.find_games_from_root(fake_steam)
        assert len(games) == 1
        g = games[0]
        assert g.name == "test game alpha"
        assert g.platform_hint == "steam"

    def test_save_dir_found(self, fake_steam):
        from src.detection.steam import SteamProvider

        sp = SteamProvider()
        install = fake_steam / "steamapps" / "common" / "Test Game Alpha"
        assert sp.find_save_dir(install) == install / "saves"


class TestEpicProvider:
    def test_manifest_parsing(self, tmp_path, monkeypatch):
        from src.detection import epic as epic_mod
        from src.detection.epic import EpicProvider

        manifests = tmp_path / "Manifests"
        manifests.mkdir()
        install = tmp_path / "Epic Games" / "BetaQuest"
        saved = install / "Saved" / "SaveGames"
        saved.mkdir(parents=True)
        (manifests / "a.item").write_text(
            json.dumps(
                {
                    "DisplayName": "beta_quest",
                    "InstallLocation": str(install),
                    "LaunchExecutable": "Beta.exe",
                }
            )
        )
        monkeypatch.setattr(epic_mod, "epic_manifest_dir", lambda: manifests)
        games = EpicProvider().find_games()
        assert len(games) == 1
        assert games[0].path == saved


class TestHeuristic:
    def test_scan_finds_save_folders(self, tmp_path):
        from src.detection.heuristic import HeuristicProvider

        root = tmp_path / "My Games"
        mystery = root / "Mystery Saga"
        mystery.mkdir(parents=True)
        for i in range(3):
            (mystery / f"slot{i}.sav").write_text("x")
        found = HeuristicProvider()._scan(root, 0)
        names = [f.name for f in found]
        assert "Mystery Saga" in names


class TestResolveExe:
    def test_falls_back_to_parent(self, tmp_path):
        from src.detection import resolve_exe_save_dir

        loose = tmp_path / "LooseGame"
        loose.mkdir()
        exe = loose / "run.exe"
        exe.write_text("x")
        hit = resolve_exe_save_dir(exe)
        assert hit.path == loose.resolve()

    def test_missing_exe_returns_none(self, tmp_path):
        from src.detection import resolve_exe_save_dir

        missing = tmp_path / "nope.exe"
        assert resolve_exe_save_dir(missing) is None


class TestDetectedGame:
    def test_dedupe_by_name_and_path(self):
        a = DetectedGame(name="X", path="C:/a", source="steam")
        b = DetectedGame(name="x", path="c:/A", source="heuristic")
        c = DetectedGame(name="Y", path="C:/b", source="steam")
        from src.detection.base import DetectionProvider

        out = DetectionProvider.dedupe([a, b, c])
        assert len(out) == 2
