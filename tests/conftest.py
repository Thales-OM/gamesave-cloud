"""Shared fixtures: isolated metadata, save folder and engine instances."""

import os
from pathlib import Path

import pytest

from src.core.engine.git_engine import GitEngine
from src.models.game import GameEntry
from src.models.metadata import Metadata


@pytest.fixture
def vault(tmp_path) -> Path:
    repos = tmp_path / "repos"
    repos.mkdir()
    return repos


@pytest.fixture
def save_dir(tmp_path) -> Path:
    d = tmp_path / "saves" / "My Game"
    d.mkdir(parents=True)
    (d / "slot1.sav").write_text("v1")
    return d


@pytest.fixture
def game(save_dir) -> GameEntry:
    return GameEntry(name="My Game", path=save_dir)


@pytest.fixture
def metadata(tmp_path, game):
    md = Metadata.load(path=tmp_path / "metadata.json")
    md.add_game(game)
    return md


@pytest.fixture
def engine(vault, game) -> GitEngine:
    return GitEngine(game=game, repos_root=vault)


def seed(path, name: str, content: str) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    f = path / name
    f.write_text(content)
    return f


def env_no_keyring(monkeypatch):
    """Force resolve_credentials to skip keyring lookups."""
    monkeypatch.setattr(
        "src.auth.credentials.load_secret", lambda *a, **k: None
    )


os.environ.setdefault("GSC_TEST", "1")
