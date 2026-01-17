# project_path/frontend/utils/key_manager.py

import json
from pathlib import Path
from typing import Dict, List, Optional

from backend.config import config


KEYS_FILE = config.STORAGE_DIR / "api_keys.json"


def _default_data() -> Dict[str, Optional[List[str]]]:
    return {"keys": [], "active_key": None}


def load_keys() -> Dict[str, Optional[List[str]]]:
    if not KEYS_FILE.exists():
        return _default_data()
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _default_data()
        data.setdefault("keys", [])
        data.setdefault("active_key", None)
        return data
    except Exception:
        return _default_data()


def save_keys(data: Dict[str, Optional[List[str]]]) -> None:
    KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def add_key(new_key: str) -> Dict[str, Optional[List[str]]]:
    data = load_keys()
    keys = data.get("keys", [])
    if new_key not in keys:
        keys.append(new_key)
    data["keys"] = keys
    data["active_key"] = new_key
    save_keys(data)
    return data


def set_active_key(active_key: str) -> Dict[str, Optional[List[str]]]:
    data = load_keys()
    if active_key in data.get("keys", []):
        data["active_key"] = active_key
        save_keys(data)
    return data
