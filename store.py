"""Where settings, profiles and sequences live on disk."""

import copy
import json
import os
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "AutoClicker"
CONFIG_PATH = APP_DIR / "config.json"

DEFAULT_PROFILE = {
    "name": "Default",
    "mode": "simple",
    "interval": {"min": 100, "max": 300, "random": False},
    "target": "cursor",
    "points": [],
    "repeat": 0,
    "steps": [],
}

DEFAULTS = {
    "hotkey": {"mods": 0, "vk": 0x75, "name": "F6"},
    "active": 0,
    "profiles": [copy.deepcopy(DEFAULT_PROFILE)],
}


def new_profile(name):
    profile = copy.deepcopy(DEFAULT_PROFILE)
    profile["name"] = name
    return profile


class Config:
    def __init__(self):
        self.data = copy.deepcopy(DEFAULTS)
        self._read()

    def _read(self):
        # The file is edited by hand often enough to assume it can be broken.
        try:
            stored = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(stored, dict):
            self.data.update({k: v for k, v in stored.items() if k in DEFAULTS})
        if not self.data["profiles"]:
            self.data["profiles"] = [copy.deepcopy(DEFAULT_PROFILE)]
        self.data["active"] = min(max(0, self.data["active"]), len(self.data["profiles"]) - 1)

    def save(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    # -- convenience
    @property
    def profiles(self):
        return self.data["profiles"]

    @property
    def profile(self):
        return self.data["profiles"][self.data["active"]]

    @property
    def hotkey(self):
        return self.data["hotkey"]


def export_steps(path, steps):
    Path(path).write_text(json.dumps({"version": 1, "steps": steps}, indent=2),
                          encoding="utf-8")


def import_steps(path):
    """Returns the step list, or raises ValueError with something readable."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"Could not read the file: {error}") from error
    steps = payload.get("steps") if isinstance(payload, dict) else payload
    if not isinstance(steps, list):
        raise ValueError("That file does not contain a sequence.")
    return steps
