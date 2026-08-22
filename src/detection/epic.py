"""Epic Games Store detection via launcher manifests."""

import json
import os
from pathlib import Path
from typing import List, Optional

from src.detection.base import DetectionProvider, DetectedGame
from src.detection.registry import register_provider


def epic_manifest_dir() -> Optional[Path]:
    base = Path(
        os.path.expandvars(
            r"%ProgramData%\Epic\EpicGamesLauncher\Data\Manifests"
        )
    )
    return base if base.is_dir() else None


@register_provider
class EpicProvider(DetectionProvider):
    name = "epic"

    def installed_games(self) -> List[dict]:
        manifest_dir = epic_manifest_dir()
        if manifest_dir is None:
            return []
        games = []
        for item in sorted(manifest_dir.glob("*.item")):
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            name = data.get("DisplayName")
            location = data.get("InstallLocation")
            if name and location and Path(location).is_dir():
                games.append(
                    {
                        "name": name,
                        "install_dir": Path(location),
                        "exe": data.get("LaunchExecutable"),
                    }
                )
        return games

    def find_games(self) -> List[DetectedGame]:
        out = []
        for app in self.installed_games():
            install_dir = app["install_dir"]
            save_dir = self.find_save_dir(install_dir) or install_dir
            exe = install_dir / app["exe"] if app.get("exe") else None
            if exe is not None and not exe.is_file():
                exe = None
            out.append(
                DetectedGame(
                    name=self.guess_display_name(app["name"]),
                    path=save_dir,
                    source=self.name,
                    exe_path=exe,
                    platform_hint="epic",
                )
            )
        return out

    def find_by_exe(self, exe_path: Path):
        exe_path = exe_path.resolve()
        for app in self.installed_games():
            install_dir = app["install_dir"].resolve()
            try:
                exe_path.relative_to(install_dir)
            except ValueError:
                continue
            save_dir = self.find_save_dir(install_dir) or install_dir
            return DetectedGame(
                name=self.guess_display_name(app["name"]),
                path=save_dir,
                source=self.name,
                exe_path=exe_path,
                platform_hint="epic",
            )
        return None
