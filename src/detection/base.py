"""Detection data models and provider base class."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel


class DetectedGame(BaseModel):
    """A game save folder discovered by a detection provider."""

    name: str
    path: Path
    source: str = "heuristic"
    exe_path: Optional[Path] = None
    platform_hint: Optional[str] = None

    def key(self) -> tuple:
        return (self.name.lower(), str(self.path).lower())


class DetectionProvider(ABC):
    """Base class for save folder discovery backends."""

    name: str = "base"

    @abstractmethod
    def find_games(self) -> List[DetectedGame]:
        """Return every detected game this provider can find."""

    # ---- shared helpers --------------------------------------------------

    SAVE_DIR_NAMES = [
        "saves",
        "save",
        "savedata",
        "savegames",
        "saved games",
        "savedsavegames",
        "gamesaves",
        "profiles",
        "slots",
    ]

    def find_save_dir(self, install_dir: Path) -> Optional[Path]:
        """Locate a save subfolder inside a game install directory.

        Scans up to two levels deep for directories whose names match
        common save-folder patterns. Returns None when nothing matches.
        """
        if not install_dir.is_dir():
            return None
        try:
            level_one = [p for p in install_dir.iterdir() if p.is_dir()]
        except OSError:
            return None
        for entry in level_one:
            if entry.name.lower() in self.SAVE_DIR_NAMES:
                return entry
        for entry in level_one:
            try:
                children = list(entry.iterdir())
            except OSError:
                continue
            for child in children:
                if child.is_dir() and child.name.lower() in (
                    self.SAVE_DIR_NAMES
                ):
                    return child
        return None

    def guess_display_name(self, raw: str) -> str:
        """Normalize a game name for display."""
        name = raw.strip()
        name = name.replace("_", " ")
        while "  " in name:
            name = name.replace("  ", " ")
        return name or "Unknown Game"

    @staticmethod
    def dedupe(games: List["DetectedGame"]) -> List["DetectedGame"]:
        seen = set()
        out = []
        for g in sorted(games, key=lambda x: x.source):
            k = g.key()
            if k in seen:
                continue
            seen.add(k)
            out.append(g)
        return out


def detect_all() -> List[DetectedGame]:
    """Run every registered provider and merge results."""
    from src.detection.registry import get_providers

    results = []
    for provider in get_providers():
        try:
            results.extend(provider.find_games())
        except Exception as ex:  # noqa: BLE001
            from src.logger import LoggerFactory

            LoggerFactory.get_logger(__name__).warning(
                "detection provider %s failed: %s", provider.name, ex
            )
    return DetectionProvider.dedupe(results)


def resolve_exe_save_dir(exe_path: Path) -> Optional[DetectedGame]:
    """Resolve the save folder for an executable path.

    Checks Steam/Epic providers first (they know install dirs), then
    falls back to heuristic scanning of the exe's parent tree.
    """
    from src.detection.registry import get_providers

    exe_path = exe_path.resolve()
    if not exe_path.is_file():
        return None
    for provider in get_providers():
        finder = getattr(provider, "find_by_exe", None)
        if finder is None:
            continue
        try:
            hit = finder(exe_path)
        except Exception:  # noqa: BLE001
            continue
        if hit is not None:
            return hit
    parent = exe_path.parent
    probe = provider_for(parent) or _HeuristicProvider()
    save_dir = probe.find_save_dir(parent)
    target = save_dir or parent
    if not target.is_dir():
        return None
    return DetectedGame(
        name=probe.guess_display_name(exe_path.stem),
        path=target,
        source="exe",
        exe_path=exe_path,
    )


def provider_for(path: Path):
    from src.detection.steam import SteamProvider
    from src.detection.epic import EpicProvider

    parts = {p.lower() for p in path.parts}
    if any("steamapps" == p or "steam" == p for p in parts):
        return SteamProvider()
    if any("epic games" in p for p in parts):
        return EpicProvider()
    return None


class _HeuristicProvider(DetectionProvider):
    name = "heuristic"

    def find_games(self) -> List[DetectedGame]:
        return []
