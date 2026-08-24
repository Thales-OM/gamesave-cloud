"""Shared fixtures: isolated metadata, save folder and engine instances."""

import os
from pathlib import Path
from typing import Any

import pytest

from src.core.engine.git_engine import GitEngine
from src.models.game import GameEntry
from src.models.metadata import Metadata


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    repos = tmp_path / "repos"
    repos.mkdir()
    return repos


@pytest.fixture
def save_dir(tmp_path: Path) -> Path:
    d = tmp_path / "saves" / "My Game"
    d.mkdir(parents=True)
    (d / "slot1.sav").write_text("v1")
    return d


@pytest.fixture
def game(save_dir: Path) -> GameEntry:
    return GameEntry(name="My Game", path=save_dir)


@pytest.fixture
def metadata(tmp_path: Path, game: GameEntry) -> Metadata:
    md = Metadata.load(path=str(tmp_path / "metadata.json"))
    md.add_game(game)
    return md


@pytest.fixture
def engine(vault: Path, game: GameEntry) -> GitEngine:
    return GitEngine(game=game, repos_root=str(vault))


def seed(path: Path, name: str, content: str) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    f = path / name
    f.write_text(content)
    return f


def env_no_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force resolve_credentials to skip keyring lookups."""

    def fake_load_secret(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr("src.auth.credentials.load_secret", fake_load_secret)


os.environ.setdefault("GSC_TEST", "1")
