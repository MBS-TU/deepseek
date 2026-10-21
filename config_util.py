"""The little configuration store for the desktop pet."""

from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path

from paths import config_path

log = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "api_key": "",
    "model": "deepseek-flash",
    "base_url": "https://api.deepseek.com/v1/chat/completions",
    "persona": "",
    "pet_x": None,
    "pet_y": None,
    "volume": 0.8,
    "short_press_ms": 280,
    "press_window_ms": 1700,
    "drag_move_px": 7,
    "mouse_idle_ms": 320,
    "key_idle_ms": 300,
}

LEGACY_MODELS = {"", "deepseek-chat", "deepseek-reasoner", "deepseek-v3"}


def _read_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        log.exception("Could not read config from %s", path)
        return {}


def _atomic_save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def load_config() -> dict:
    path = config_path()
    raw = _read_json(path)
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg.update(raw)

    # The previous scaffold used deepseek-chat.  V4.1 Flash is exposed as
    # "deepseek-flash" by the DeepSeek API.
    if str(cfg.get("model", "")).strip().lower() in LEGACY_MODELS:
        cfg["model"] = "deepseek-flash"

    cfg["api_key"] = str(cfg.get("api_key", "")).strip()
    cfg["base_url"] = str(cfg.get("base_url", "")).strip() or DEFAULT_CONFIG["base_url"]
    cfg["model"] = str(cfg.get("model", "")).strip() or DEFAULT_CONFIG["model"]
    cfg["persona"] = str(cfg.get("persona", "") or "")

    # Numeric sanity, in case a user edits the JSON by hand.
    cfg["volume"] = max(0.0, min(1.0, _as_float(cfg.get("volume"), 0.8)))
    cfg["short_press_ms"] = max(80, _as_int(cfg.get("short_press_ms"), 280))
    cfg["press_window_ms"] = max(500, _as_int(cfg.get("press_window_ms"), 1700))
    cfg["drag_move_px"] = max(2, _as_int(cfg.get("drag_move_px"), 7))
    cfg["mouse_idle_ms"] = max(80, _as_int(cfg.get("mouse_idle_ms"), 320))
    cfg["key_idle_ms"] = max(80, _as_int(cfg.get("key_idle_ms"), 300))

    for key in ("pet_x", "pet_y"):
        cfg[key] = _as_int(cfg.get(key), None)

    if cfg != raw:
        try:
            save_config(cfg)
        except Exception:
            log.exception("Could not write normalized config")
    return cfg


def save_config(cfg: dict) -> None:
    data = copy.deepcopy(DEFAULT_CONFIG)
    data.update(cfg or {})
    _atomic_save(config_path(), data)


def _as_int(value, fallback: int | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _as_float(value, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def has_api_key(cfg: dict) -> bool:
    return bool(str(cfg.get("api_key", "")).strip())
