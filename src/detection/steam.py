"""Steam library detection via registry + appmanifest files."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.detection.base import DetectionProvider, DetectedGame
from src.detection.registry import register_provider
from src.detection.vdf import parse_vdf

STEAM_REGISTRY_KEYS = [
    (r"Software\Valve\Steam", "SteamPath"),
    (r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
]


def find_steam_root() -> Optional[Path]:
    """Locate the Steam installation folder."""
    if os.name == "nt":
        import winreg

        for key_path, value_name in STEAM_REGISTRY_KEYS:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    raw, _ = winreg.QueryValueEx(key, value_name)
                    candidate = Path(raw)
                    if candidate.is_dir():
                        return candidate
            except OSError:
                continue
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    raw, _ = winreg.QueryValueEx(key, value_name)
                    candidate = Path(raw)
                    if candidate.is_dir():
                        return candidate
            except OSError:
                continue
    fallback = Path(os.path.expandvars(r"%ProgramFiles(x86)%\Steam"))
    return fallback if fallback.is_dir() else None


def steam_libraries(steam_root: Path) -> List[Path]:
    """Return every configured Steam library folder."""
    libraries = [steam_root]
    vdf_path = steam_root / "steamapps" / "libraryfolders.vdf"
    if vdf_path.is_file():
        try:
            data = parse_vdf(vdf_path.read_text(encoding="utf-8", errors="replace"))
            folders = data.get("libraryfolders", {})
            for entry in folders.values():
                if isinstance(entry, dict):
                    p = entry.get("path")
                    if p and Path(p).is_dir():
                        libraries.append(Path(p))
        except OSError:
            pass
    unique: List[Path] = []
    for lib in libraries:
        if lib not in unique:
            unique.append(lib)
    return unique


def read_appmanifests(library: Path) -> List[Dict[str, Any]]:
    """Parse every appmanifest_*.acf in a library."""
    apps: List[Dict[str, Any]] = []
    apps_dir = library / "steamapps"
    if not apps_dir.is_dir():
        return apps
    for acf in sorted(apps_dir.glob("appmanifest_*.acf")):
        try:
            data = parse_vdf(acf.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        app = data.get("AppState")
        if not isinstance(app, dict):
            continue
        name = app.get("name") or app.get("userconfig", {}).get("name")
        installdir = app.get("installdir")
        if name and installdir:
            apps.append(
                {
                    "appid": app.get("appid"),
                    "name": name,
                    "installdir": installdir,
                    "library": library,
                }
            )
    return apps


@register_provider
class SteamProvider(DetectionProvider):
    name = "steam"

    def installed_games(self) -> List[Dict[str, Any]]:
        root = find_steam_root()
        if root is None:
            return []
        games = []
        for lib in steam_libraries(root):
            games.extend(read_appmanifests(lib))
        return games

    def find_games(self) -> List[DetectedGame]:
        root = find_steam_root()
        if root is None:
            return []
        return self.find_games_from_root(root)

    def find_games_from_root(self, root: Path) -> List[DetectedGame]:
        out = []
        for lib in steam_libraries(root):
            for app in read_appmanifests(lib):
                install_dir = (
                    Path(app["library"]) / "steamapps" / "common" / app["installdir"]
                )
                save_dir = self.find_save_dir(install_dir) or install_dir
                exe = self._first_exe(install_dir)
                out.append(
                    DetectedGame(
                        name=self.guess_display_name(app["name"]),
                        path=save_dir,
                        source=self.name,
                        exe_path=exe,
                        platform_hint="steam",
                    )
                )
        return out

    def find_by_exe(self, exe_path: Path) -> Optional[DetectedGame]:
        """Match an executable against known Steam installs."""
        exe_path = exe_path.resolve()
        for app in self.installed_games():
            install_dir = (
                Path(app["library"]) / "steamapps" / "common" / app["installdir"]
            ).resolve()
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
                platform_hint="steam",
            )
        return None

    @staticmethod
    def _first_exe(install_dir: Path) -> Optional[Path]:
        try:
            exes = sorted(install_dir.glob("*.exe"))
            return exes[0] if exes else None
        except OSError:
            return None
