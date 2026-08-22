"""Provider registry for save folder detection."""

from typing import List

from src.detection.base import DetectionProvider

_PROVIDERS = []


def register_provider(provider_class):
    _PROVIDERS.append(provider_class())
    return provider_class


def get_providers() -> List[DetectionProvider]:
    if not _PROVIDERS:
        from src.detection.steam import SteamProvider  # noqa: F401
        from src.detection.epic import EpicProvider  # noqa: F401
        from src.detection.heuristic import HeuristicProvider  # noqa: F401

    return list(_PROVIDERS)
