"""Heuristic detection of save folders in well-known locations."""

from pathlib import Path
from typing import List

from src.detection.base import DetectionProvider, DetectedGame
from src.detection.registry import register_provider


def known_save_roots() -> List[Path]:
    home = Path.home()
    candidates = [
        home / "Saved Games",
        home / "Documents" / "My Games",
        Path(os_localappdata()) / "Saved Games",
    ]
    docs = home / "Documents"
    if docs.is_dir():
        candidates.append(docs)
    return [c for c in candidates if c.is_dir()]


def os_localappdata() -> str:
    import os

    return os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData"))


@register_provider
class HeuristicProvider(DetectionProvider):
    name = "heuristic"

    MAX_DEPTH = 2

    def find_games(self) -> List[DetectedGame]:
        out = []
        for root in known_save_roots():
            out.extend(self._scan(root, depth=0))
        return out

    def _scan(self, folder: Path, depth: int) -> List[DetectedGame]:
        found: List[DetectedGame] = []
        try:
            entries = sorted(p for p in folder.iterdir() if p.is_dir())
        except OSError:
            return found
        for child in entries:
            if self._looks_like_save_folder(child):
                found.append(
                    DetectedGame(
                        name=self.guess_display_name(child.name),
                        path=child,
                        source=self.name,
                    )
                )
            elif depth < self.MAX_DEPTH and not child.name.startswith((".", "$")):
                found.extend(self._scan(child, depth + 1))
        return found

    @staticmethod
    def _looks_like_save_folder(folder: Path) -> bool:
        name = folder.name.lower()
        markers = (
            "save",
            "slot",
            "profile",
            "backup",
        )
        if any(m in name for m in markers):
            return True
        try:
            children = list(folder.iterdir())
        except OSError:
            return False
        files = [
            c
            for c in children
            if c.is_file()
            and c.suffix.lower()
            in (
                ".sav",
                ".save",
                ".bak",
                ".dat",
                ".bin",
                ".json",
                ".xml",
            )
        ]
        return len(files) >= 2
