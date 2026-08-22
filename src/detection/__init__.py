"""Save folder detection providers."""

from src.detection.base import DetectedGame, detect_all, resolve_exe_save_dir
from src.detection.registry import get_providers, register_provider

__all__ = [
    "DetectedGame",
    "DetectionProvider",
    "detect_all",
    "resolve_exe_save_dir",
    "get_providers",
    "register_provider",
]
