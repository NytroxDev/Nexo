import json
from pathlib import Path


CONFIG_DIR = Path.home() / ".config" / "nexo"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "target": "127.0.0.1:9000",
    "receive_dir": str(Path.home() / "Downloads"),
    "geometry": "680x480",
}


def load() -> dict:
    try:
        with open(CONFIG_FILE) as f:
            return {**DEFAULTS, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULTS)


def save(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    current = load()
    current.update(data)
    with open(CONFIG_FILE, "w") as f:
        json.dump(current, f, indent=2)
