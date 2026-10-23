"""Where settings, profiles and sequences live on disk."""

import copy
import json
import os
import re
from datetime import datetime
from pathlib import Path

_ROAMING = Path(os.environ.get("APPDATA", Path.home()))
# Everything Auto Clicker keeps (config.json, images\, move.log) lives here since 1.1.0, beside the other
# Protagonist Labs apps. Before, it was %APPDATA%\AutoClicker; move_old_data() moves it.
APP_DIR = _ROAMING / "ProtagonistLabs" / "Auto Clicker"
OLD_DIR = _ROAMING / "AutoClicker"


def move_old_data():
    """Called once at start, before anything is read. The old folder moves with one rename (same volume,
    instant): never a partial copy. If the new folder already holds data nothing is mixed: the old one
    stays and move.log says so. If the rename fails (a file in use), this session reads and writes the
    old folder, and the next start tries again."""
    global APP_DIR
    if not OLD_DIR.is_dir():
        return
    try:
        if APP_DIR.is_dir() and any(APP_DIR.iterdir()):
            _log(f"kept {OLD_DIR}: {APP_DIR} already holds data")
            return
        APP_DIR.parent.mkdir(parents=True, exist_ok=True)
        if APP_DIR.is_dir():
            APP_DIR.rmdir()
        os.rename(OLD_DIR, APP_DIR)
        _log(f"moved {OLD_DIR} to {APP_DIR}")
    except OSError:
        APP_DIR = OLD_DIR  # not logged: a log would make the new folder look taken


def _log(line):
    try:
        with open(APP_DIR / "move.log", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {line}\n")
    except OSError:
        pass


def _moved(text):
    """Image steps keep absolute paths to images: ones still under the old folder point at the new one.
    Works on the JSON text, so steps nested in loops and conditions are covered too."""
    if APP_DIR == OLD_DIR:
        return text
    old = json.dumps(str(OLD_DIR) + os.sep)[1:-1]
    new = json.dumps(str(APP_DIR) + os.sep)[1:-1]
    return re.sub(re.escape(old), lambda _: new, text, flags=re.IGNORECASE)


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
    "whatsnew_seen": None,  # the last version whose What's new was closed
}


def new_profile(name):
    profile = copy.deepcopy(DEFAULT_PROFILE)
    profile["name"] = name
    return profile


class Config:
    def __init__(self):
        self.data = copy.deepcopy(DEFAULTS)
        self.existed = (APP_DIR / "config.json").is_file()  # Auto Clicker ran here before
        self._read()

    def _read(self):
        # The file is edited by hand often enough to assume it can be broken.
        try:
            stored = json.loads(_moved((APP_DIR / "config.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return
        if isinstance(stored, dict):
            self.data.update({k: v for k, v in stored.items() if k in DEFAULTS})
        if not self.data["profiles"]:
            self.data["profiles"] = [copy.deepcopy(DEFAULT_PROFILE)]
        self.data["active"] = min(max(0, self.data["active"]), len(self.data["profiles"]) - 1)

    def save(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        (APP_DIR / "config.json").write_text(json.dumps(self.data, indent=2), encoding="utf-8")

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
        payload = json.loads(_moved(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        raise ValueError(f"Could not read the file: {error}") from error
    steps = payload.get("steps") if isinstance(payload, dict) else payload
    if not isinstance(steps, list):
        raise ValueError("That file does not contain a sequence.")
    return steps
