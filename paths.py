"""Filesystem paths used by both the source tree and the frozen executable."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "肥鱼桌宠"
APP_INTERNAL_NAME = "FeiyuDeep"
APP_ID = "FeiyuDeep.DesktopPet"
APP_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Folder that contains the bundled assets (works in onefile mode)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return PROJECT_ROOT


def asset_path(*parts: str) -> Path:
    return resource_root().joinpath("assets", *parts)


def _config_dir_override() -> Path | None:
    override = (os.environ.get("FEIYU_CONFIG_DIR")
                or os.environ.get("LAOZHOU_CONFIG_DIR"))
    return Path(override).expanduser() if override else None


def config_dir() -> Path:
    override = _config_dir_override()
    if override:
        return override
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_INTERNAL_NAME
    return Path.home() / ".config" / APP_INTERNAL_NAME


def config_path() -> Path:
    """Use the project config while developing; AppData for the packaged app."""
    override = _config_dir_override()
    if override:
        return override / "config.json"
    if not is_frozen():
        local = PROJECT_ROOT / "config.json"
        if local.exists():
            return local
    return config_dir() / "config.json"


def log_path() -> Path:
    folder = config_dir() / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "feiyu.log"


def legacy_config_paths() -> list[Path]:
    """Previous-brand config locations, used only for a one-time local import."""
    paths: list[Path] = []
    if _config_dir_override():
        return paths
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(Path(appdata) / "Laozhou325" / "config.json")
    return paths
