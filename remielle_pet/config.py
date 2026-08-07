import json
from pathlib import Path

from .constants import CONFIG_PATH, DEFAULT_CONFIG


def load_config(path: Path | None = None) -> dict:
    target = path or CONFIG_PATH
    data = dict(DEFAULT_CONFIG)
    if target.exists():
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update({key: loaded[key] for key in DEFAULT_CONFIG if key in loaded})
        except (OSError, json.JSONDecodeError):
            pass
    return data


def save_config(config: dict, path: Path | None = None) -> None:
    target = path or CONFIG_PATH
    safe = {key: config.get(key, value) for key, value in DEFAULT_CONFIG.items()}
    target.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
