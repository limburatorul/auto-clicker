"""Auto Clicker - clicks where the cursor is, or runs a sequence you built."""

import ctypes
import hashlib
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
import urllib.request
from ctypes import wintypes

from PySide6.QtCore import QObject, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (QColor, QDesktopServices, QIcon, QKeySequence,
                           QPainter, QPalette, QPen)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
                               QHBoxLayout, QInputDialog, QLabel, QListWidget,
                               QMenu, QMessageBox, QPushButton, QSpinBox,
                               QTabWidget, QVBoxLayout, QWidget)

import editor
import engine
import store
import theme
import winapi

VERSION = "1.0.10"
RELEASES = "https://api.github.com/repos/limburatorul/auto-clicker/releases/latest"

HOTKEY_ID = 1
WM_NCHITTEST = 0x0084
BORDER = 6
HIT_CODES = {(True, False, True, False): 13, (True, False, False, True): 14,
             (False, True, True, False): 16, (False, True, False, True): 17,
             (True, False, False, False): 12, (False, True, False, False): 15,
             (False, False, True, False): 10, (False, False, False, True): 11}


_waiting = None  # the version swapped in and waiting for the next start


def update_in_place():
    """Auto Clicker is one portable .exe, so it updates itself in place: the newest GitHub release's .exe
    is downloaded beside the running one, checked against the size and SHA-256 GitHub published for it,
    and swapped in. Windows lets a running .exe be renamed, so the old one steps aside as <name>.old
    (deleted at the next start) and nothing has to close; the next start is the new version. Returns
    that version, or None: run from source, up to date, offline, or a folder it may not write to."""
    global _waiting
    # Already swapped in: the running copy is now the .old, so a second download could never be
    # swapped in and would only cost another 88 MB every check. Nothing more until the next start.
    if _waiting:
        return _waiting
    if not getattr(sys, "frozen", False):
        return None
    exe = sys.executable
    try:
        os.remove(exe + ".old")
    except OSError:
        pass
    fresh = exe + ".new"
    try:
        request = urllib.request.Request(RELEASES, headers={"User-Agent": "Auto Clicker"})
        with urllib.request.urlopen(request, timeout=30) as r:
            release = json.load(r)
        tag = release["tag_name"].lstrip("vV")
        if tuple(map(int, tag.split("."))) <= tuple(map(int, VERSION.split("."))):
            return None
        asset = next(a for a in release["assets"] if a["name"].lower().endswith(".exe"))
        digest = asset.get("digest") or ""
        if not digest.startswith("sha256:"):
            return None  # nothing to check it against: never run
        sha = hashlib.sha256()
        with urllib.request.urlopen(asset["browser_download_url"], timeout=60) as r, open(fresh, "wb") as f:
            while chunk := r.read(1 << 16):
                f.write(chunk)
                sha.update(chunk)
        # the size catches a cut-off download, the checksum everything else
        if os.path.getsize(fresh) != asset["size"] or sha.hexdigest() != digest[7:].lower():
            os.remove(fresh)
            return None
        os.replace(exe, exe + ".old")
        try:
            os.replace(fresh, exe)
        except OSError:
            os.replace(exe + ".old", exe)  # never leave the folder without its .exe
            raise
        _waiting = tag
        return tag
    except (OSError, ValueError, KeyError, StopIteration):
        try:
            os.remove(fresh)
        except OSError:
            pass
        return None


# -- the Protagonist Labs apps ----------------------------------------------
# They find each other through %APPDATA%\ProtagonistLabs: each one writes a card about itself into
# apps\. Auto Clicker writes its own and reads HotkeyScan's, which can name the app holding a taken
# hotkey. A card that is missing, malformed or points at an exe that is gone means "not installed".
SHARED_APPS = os.path.join(os.environ.get("APPDATA", ""), "ProtagonistLabs", "apps")
PAID = (("shelf", "Shelf"), ("stash", "Stash"), ("frostpane", "Frostpane"), ("reel", "Reel"),
        ("planner", "Planner"), ("reminder", "Reminder"))
UTM = "utm_source=autoclicker&utm_medium=app&utm_campaign=works-with"
# HotkeyScan's names for the keys that are not a letter, a digit or an F-key
HOTKEYSCAN_KEYS = {0x20: "Space", 0x09: "Tab", 0x0D: "Enter", 0x08: "Backspace", 0x2D: "Insert",
                   0x2E: "Delete", 0x24: "Home", 0x23: "End", 0x21: "PageUp", 0x22: "PageDown",
                   0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down", 0x2C: "PrintScreen",
                   0x13: "Pause", 0x91: "ScrollLock", 0x14: "CapsLock", 0x90: "NumLock", 0x5D: "Apps",
                   0x6A: "NumMul", 0x6B: "NumAdd", 0x6D: "NumSub", 0x6E: "NumDec", 0x6F: "NumDiv",
                   0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/", 0xC0: "`",
                   0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'", 0xAD: "VolumeMute", 0xAE: "VolumeDown",
                   0xAF: "VolumeUp", 0xB0: "MediaNext", 0xB1: "MediaPrev", 0xB2: "MediaStop", 0xB3: "MediaPlayPause"}


def read_card(app_id):
    try:
        with open(os.path.join(SHARED_APPS, app_id + ".json"), encoding="utf-8-sig") as f:
            card = json.load(f)
        if card.get("schema") == 1 and isinstance(card.get("exe"), str) and os.path.isfile(card["exe"]):
            return card
    except (OSError, ValueError, AttributeError):
        pass
    return None


def write_card():
    if not getattr(sys, "frozen", False):
        return  # run from source it is python.exe, which no sister should ever start
    card = {"schema": 1, "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "id": "autoclicker", "name": "Auto Clicker", "version": VERSION, "exe": sys.executable,
            "edition": "free", "paid": False, "page": "https://protagonistlabs.app/autoclicker/",
            "commands": {}}
    path = os.path.join(SHARED_APPS, "autoclicker.json")
    try:
        os.makedirs(SHARED_APPS, exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(card, f, indent=2)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def hotkeyscan_combo(hotkey):
    """Auto Clicker names keys the way Qt prints them ("Ctrl+!" for Ctrl+Shift+1); HotkeyScan wants
    the key itself, so the name is rebuilt from the modifiers and the virtual-key code."""
    parts = [name for bit, name in ((winapi.MOD_CONTROL, "Ctrl"), (winapi.MOD_ALT, "Alt"),
                                    (winapi.MOD_SHIFT, "Shift"), (winapi.MOD_WIN, "Win"))
             if hotkey["mods"] & bit]
    vk = hotkey["vk"]
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        parts.append(chr(vk))
    elif 0x70 <= vk <= 0x87:
        parts.append(f"F{vk - 0x6F}")
    elif 0x60 <= vk <= 0x69:
        parts.append(f"Num{vk - 0x60}")
    else:
        parts.append(HOTKEYSCAN_KEYS.get(vk, hotkey["name"].split("+")[-1]))
    return "+".join(parts)


def works_with_html(link):
    """The footer's Works with: HotkeyScan, and one quiet line of 30% off for owners of a paid app."""
    cards = {app_id: read_card(app_id) for app_id in ("hotkeyscan",) + tuple(p[0] for p in PAID)}
    if cards["hotkeyscan"]:
        lines = ["HotkeyScan · shows which app holds a taken hotkey"]
    else:
        lines = [f'<a {link} href="https://protagonistlabs.app/hotkeyscan/?{UTM}">HotkeyScan</a>'
                 " · would show which app holds a taken hotkey"]
    bought = any(c and c.get("paid") is True and c.get("edition") == "full" for c in cards.values())
    missing = [(i, n) for i, n in PAID if not cards[i]][:4]
    if bought and missing:
        names = " · ".join(f'<a {link} href="https://protagonistlabs.app/{i}/?code='
                           f'{"SECOND30SHELF" if i == "shelf" else "SECOND30"}&{UTM}">{n}</a>'
                           for i, n in missing)
        lines.append("Owners of one of our apps get 30% off the others: " + names)
    return "Works with<br>" + "<br>".join(lines)


class _Updated(QObject):
    """Carries the result of the background update back to the window's thread."""
    done = Signal(str)


class AutoClicker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto Clicker")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(400, 660)
        self.setMinimumSize(380, 560)

        self.config = store.Config()
        self.runner = None
        self._note = ""  # why the last run did less than expected; stays until the next Start

        self._build()
        self._load_profile()

    # -- chrome ------------------------------------------------------------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._title_bar())

        body = QVBoxLayout()
        body.setContentsMargins(16, 4, 16, 14)
        body.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._clicker_tab(), "Clicker")
        self.tabs.addTab(self._sequence_tab(), "Sequence")
        self.tabs.currentChanged.connect(self._mode_changed)
        body.addWidget(self.tabs, 1)

        self.hotkey_btn = QPushButton(self.config.hotkey["name"], objectName="hotkeyBtn")
        self.hotkey_btn.setCheckable(True)
        self.hotkey_btn.setFixedWidth(152)
        self.hotkey_btn.clicked.connect(self._capture_hotkey)
        self.hotkey_btn.keyPressEvent = self._hotkey_key
        body.addWidget(self._card("HOTKEY", self.hotkey_btn))

        self.toggle_btn = QPushButton("Start", objectName="toggleBtn")
        self.toggle_btn.setProperty("running", "false")
        self.toggle_btn.setFocusPolicy(Qt.NoFocus)
        self.toggle_btn.clicked.connect(self.toggle)
        body.addWidget(self.toggle_btn)

        self.status = QLabel("", objectName="status")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setTextInteractionFlags(Qt.LinksAccessibleByMouse)
        self.status.linkActivated.connect(self._see_who_holds)
        self.status.setWordWrap(True)  # a note plus the hint is longer than the window
        body.addWidget(self.status)

        link = 'style="color: rgba(232,234,237,0.7);"'
        links = QLabel(
            f'<a {link} href="https://protagonistlabs.app/autoclicker/?utm_source=autoclicker&utm_medium=app&utm_campaign=footer">Website</a>'
            f' · Feedback: <a {link} href="mailto:feedback@protagonistlabs.app?subject=Auto%20Clicker%20feedback">feedback@protagonistlabs.app</a>'
            f'<br><a {link} href="https://protagonistlabs.app/?utm_source=autoclicker&utm_medium=app&utm_campaign=more-apps">More apps from Protagonist Labs</a>',
            objectName="hint")
        links.setAlignment(Qt.AlignCenter)
        links.setWordWrap(True)
        links.setOpenExternalLinks(True)  # QDesktopServices.openUrl
        links.setTextInteractionFlags(Qt.TextBrowserInteraction)  # the address can be selected and copied
        body.addWidget(links)

        # The sister apps, read from their cards off the UI thread.
        self.works = QLabel("", objectName="hint")
        self.works.setAlignment(Qt.AlignCenter)
        self.works.setWordWrap(True)
        self.works.setOpenExternalLinks(True)
        self.works.hide()
        body.addWidget(self.works)
        self._works_done = _Updated()
        self._works_done.done.connect(self._on_works_with)
        quiet = 'style="color: rgba(232,234,237,0.45); text-decoration: none;"'
        threading.Thread(target=lambda: (write_card(), self._works_done.done.emit(works_with_html(quiet))),
                         daemon=True).start()

        # Shown after the first run: one app we make, with a code for Auto Clicker's users.
        self.offer = QLabel(
            f'Play PC games? <a {link} href="https://protagonistlabs.app/shelf/?code=FREEAPP30&utm_source=autoclicker'
            f'&utm_medium=app&utm_campaign=recommend#pricing">Shelf</a>, our game library that also backs up '
            f'your saves, is 30% off for Auto Clicker users.', objectName="hint")
        self.offer.setAlignment(Qt.AlignCenter)
        self.offer.setWordWrap(True)
        self.offer.setOpenExternalLinks(True)
        self.offer.hide()
        body.addWidget(self.offer)

        self.updated = QLabel("", objectName="hint")
        self.updated.setAlignment(Qt.AlignCenter)
        self.updated.setWordWrap(True)
        self.updated.hide()
        body.addWidget(self.updated)
        self._update_done = _Updated()
        self._update_done.done.connect(self._on_updated)
        self._check_update()
        # the window may stay open for days: a release published meanwhile is fetched within the hour
        self._update_timer = QTimer(self, interval=3600 * 1000, timeout=self._check_update)
        self._update_timer.start()

        root.addLayout(body)
        self._set_status()

    def _title_bar(self):
        bar = QWidget(objectName="titleBar")
        bar.setFixedHeight(40)
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 0, 8, 0)
        row.setSpacing(6)
        row.addWidget(QLabel("Auto Clicker", objectName="title"))

        self.profiles = QComboBox()
        self.profiles.setFixedWidth(120)
        self.profiles.currentIndexChanged.connect(self._switch_profile)
        row.addWidget(self.profiles)

        self.profile_menu_btn = QPushButton("⋯", objectName="stepBtn")
        self.profile_menu_btn.setFocusPolicy(Qt.NoFocus)
        self.profile_menu_btn.clicked.connect(self._profile_menu)
        row.addWidget(self.profile_menu_btn)
        row.addStretch()

        minimise = QPushButton("─", objectName="winBtn")
        minimise.setFocusPolicy(Qt.NoFocus)
        minimise.clicked.connect(self.showMinimized)
        close = QPushButton("✕", objectName="closeBtn")
        close.setFocusPolicy(Qt.NoFocus)
        close.clicked.connect(self.close)
        row.addWidget(minimise)
        row.addWidget(close)
        bar.mousePressEvent = self._start_drag
        return bar

    def _card(self, label, control):
        card = QFrame(objectName="card")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 10, 12, 10)
        row.addWidget(QLabel(label, objectName="cardLabel"))
        row.addStretch()
        row.addWidget(control)
        return card

    def _stepper(self, spin):
        """The spin box' own arrows are drawn by the native style and vanish on
        a dark translucent field, so it gets explicit - / + buttons instead."""
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        for text, step in (("−", spin.stepDown), ("+", spin.stepUp)):
            button = QPushButton(text, objectName="stepBtn")
            button.setFocusPolicy(Qt.NoFocus)
            button.setAutoRepeat(True)
            button.setAutoRepeatDelay(400)
            button.setAutoRepeatInterval(60)
            button.clicked.connect(step)
            row.addWidget(button)
        row.insertWidget(1, spin)
        return holder

    # -- tabs --------------------------------------------------------------
    def _clicker_tab(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 10, 0, 0)
        column.setSpacing(10)

        self.interval_min = editor.DurationBox()
        self.interval_min.valueChanged.connect(self._interval_changed)
        column.addWidget(self._card("INTERVAL", self._stepper(self.interval_min)))

        random_card = QFrame(objectName="card")
        random_row = QVBoxLayout(random_card)
        random_row.setContentsMargins(14, 10, 12, 10)
        random_row.setSpacing(8)
        head = QHBoxLayout()
        self.random_check = QCheckBox("Random up to")
        self.random_check.stateChanged.connect(self._interval_changed)
        head.addWidget(self.random_check)
        head.addStretch()
        self.interval_max = editor.DurationBox()
        self.interval_max.valueChanged.connect(self._interval_changed)
        head.addWidget(self.interval_max)
        random_row.addLayout(head)
        self.random_card = random_card
        column.addWidget(random_card)

        points_card = QFrame(objectName="card")
        points_col = QVBoxLayout(points_card)
        points_col.setContentsMargins(14, 10, 12, 12)
        points_col.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(QLabel("CLICK AT", objectName="cardLabel"))
        head.addStretch()
        self.target = QComboBox()
        self.target.addItem("Wherever the cursor is", "cursor")
        self.target.addItem("A list of points", "points")
        self.target.setFixedWidth(184)
        self.target.currentIndexChanged.connect(self._target_changed)
        head.addWidget(self.target)
        points_col.addLayout(head)

        self.points = QListWidget()
        self.points.setMaximumHeight(120)
        points_col.addWidget(self.points)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.add_point_btn = QPushButton("Add point", objectName="plainBtn")
        self.add_point_btn.clicked.connect(self._add_point)
        self.remove_point_btn = QPushButton("Remove", objectName="plainBtn")
        self.remove_point_btn.clicked.connect(self._remove_point)
        buttons.addWidget(self.add_point_btn)
        buttons.addWidget(self.remove_point_btn)
        buttons.addStretch()
        points_col.addLayout(buttons)
        self.points_card = points_card
        column.addWidget(points_card)
        column.addStretch()
        return page

    def _sequence_tab(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 10, 0, 0)
        column.setSpacing(10)

        head = QHBoxLayout()
        head.addWidget(QLabel("STEPS", objectName="cardLabel"))
        head.addStretch()
        head.addWidget(QLabel("Repeat", objectName="hint"))
        self.repeat = QSpinBox()
        self.repeat.setRange(0, 100000)
        self.repeat.setFixedWidth(72)
        self.repeat.setSpecialValueText("∞")
        self.repeat.valueChanged.connect(self._repeat_changed)
        head.addWidget(self.repeat)
        column.addLayout(head)

        self.sequence = editor.SequenceEditor()
        self.sequence.changed.connect(self._sequence_changed)
        column.addWidget(self.sequence, 1)

        files = QHBoxLayout()
        files.setSpacing(6)
        self.save_seq_btn = QPushButton("Save…", objectName="plainBtn")
        self.save_seq_btn.clicked.connect(self.sequence.save_to_file)
        self.load_seq_btn = QPushButton("Load…", objectName="plainBtn")
        self.load_seq_btn.clicked.connect(self.sequence.load_from_file)
        files.addStretch()
        files.addWidget(self.save_seq_btn)
        files.addWidget(self.load_seq_btn)
        column.addLayout(files)
        return page

    # -- profiles ----------------------------------------------------------
    def _load_profile(self):
        self.profiles.blockSignals(True)
        self.profiles.clear()
        for profile in self.config.profiles:
            self.profiles.addItem(profile["name"])
        self.profiles.setCurrentIndex(self.config.data["active"])
        self.profiles.blockSignals(False)

        profile = self.config.profile
        for widget in (self.interval_min, self.interval_max, self.random_check,
                       self.target, self.repeat):
            widget.blockSignals(True)
        self.interval_min.setValue(profile["interval"]["min"])
        self.interval_max.setValue(profile["interval"]["max"])
        self.random_check.setChecked(profile["interval"].get("random", False))
        self.target.setCurrentIndex(1 if profile.get("target") == "points" else 0)
        self.repeat.setValue(profile.get("repeat", 0))
        for widget in (self.interval_min, self.interval_max, self.random_check,
                       self.target, self.repeat):
            widget.blockSignals(False)

        self.points.clear()
        for x, y in profile.get("points", []):
            self.points.addItem(f"{x}, {y}")
        self.sequence.set_steps(profile.setdefault("steps", []))
        self.tabs.setCurrentIndex(1 if profile.get("mode") == "sequence" else 0)
        self._target_changed()

    def _switch_profile(self, index):
        if index < 0:
            return
        self.config.save()
        self.config.data["active"] = index
        self._load_profile()

    def _profile_menu(self):
        menu = QMenu(self)
        menu.addAction("New profile", self._new_profile)
        menu.addAction("Rename…", self._rename_profile)
        menu.addAction("Delete", self._delete_profile)
        menu.exec(self.profile_menu_btn.mapToGlobal(self.profile_menu_btn.rect().bottomLeft()))

    def _ask_name(self, title, initial=""):
        name, ok = QInputDialog.getText(self, title, "Name", text=initial)
        return name.strip() if ok else ""

    def _new_profile(self):
        name = self._ask_name("New profile", f"Profile {len(self.config.profiles) + 1}")
        if not name:
            return
        self.config.profiles.append(store.new_profile(name))
        self.config.data["active"] = len(self.config.profiles) - 1
        self.config.save()
        self._load_profile()

    def _rename_profile(self):
        name = self._ask_name("Rename profile", self.config.profile["name"])
        if not name:
            return
        self.config.profile["name"] = name
        self.config.save()
        self._load_profile()

    def _delete_profile(self):
        if len(self.config.profiles) == 1:
            QMessageBox.information(self, "Delete profile", "The last profile stays.")
            return
        del self.config.profiles[self.config.data["active"]]
        self.config.data["active"] = 0
        self.config.save()
        self._load_profile()

    # -- clicker settings --------------------------------------------------
    def _interval_changed(self, *_):
        interval = self.config.profile["interval"]
        interval["min"] = self.interval_min.value()
        interval["max"] = self.interval_max.value()
        interval["random"] = self.random_check.isChecked()
        self.interval_max.setEnabled(self.random_check.isChecked())
        self.config.save()
        if self.runner and self.runner.isRunning():
            self.status.setText("Restart for the new interval to apply")

    def _target_changed(self, *_):
        self.config.profile["target"] = self.target.currentData()
        self.interval_max.setEnabled(self.random_check.isChecked())
        self.config.save()

    def _add_point(self):
        self.hide()

        def done(point):  # None when the user pressed Esc - the window still returns
            if point is not None:
                if self.target.currentData() != "points":
                    self.target.setCurrentIndex(1)  # picking a point implies using the list
                self.config.profile.setdefault("points", []).append([point[0], point[1]])
                self.points.addItem(f"{point[0]}, {point[1]}")
                self.config.save()
            self.show()

        editor.pick_point(done)

    def _remove_point(self):
        row = self.points.currentRow()
        if row < 0:
            return
        self.points.takeItem(row)
        del self.config.profile["points"][row]
        self.config.save()

    def _repeat_changed(self, value):
        self.config.profile["repeat"] = value
        self.config.save()

    def _sequence_changed(self):
        self.config.profile["steps"] = self.sequence.steps
        self.config.save()

    def _mode_changed(self, index):
        self.config.profile["mode"] = "sequence" if index == 1 else "simple"
        # Saved on every change, not only on close: the app can be killed while
        # a sequence is running and the settings should survive that.
        self.config.save()
        self._set_status()

    # -- running -----------------------------------------------------------
    def toggle(self):
        if self.runner and self.runner.isRunning():
            self.runner.stop()
            return
        if self.tabs.currentIndex() == 1:
            steps = self.config.profile.get("steps", [])
            repeat = self.config.profile.get("repeat", 0)
            if not steps:
                self.status.setText("Add a step first")
                return
        else:
            steps, repeat = engine.simple_steps(self.config.profile), 0
            if self.config.profile.get("target") == "points" \
                    and not self.config.profile.get("points"):
                self.status.setText("Add a point first")
                return

        self._note = ""
        self.runner = engine.Runner(steps, repeat)
        self.runner.counted.connect(self._on_count)
        self.runner.note.connect(self._on_note)
        self.runner.stopped.connect(self._on_stopped)
        self.runner.start()
        self._set_running(True)

    def _set_running(self, running):
        self.toggle_btn.setText("Stop" if running else "Start")
        self.toggle_btn.setProperty("running", "true" if running else "false")
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)
        self._set_status()

    def _on_count(self, count):
        self._show(f"Running · {count} clicks · {self.config.hotkey['name']} to stop")

    def _on_note(self, text):
        if not self._note:  # the first note of a run is the cause; later ones follow from it
            self._note = text
            self._set_status()

    def _show(self, text):
        self.status.setText(f"{self._note} · {text}" if self._note else text)

    def _on_stopped(self):
        self._set_running(False)
        self.offer.show()

    def _check_update(self):
        threading.Thread(target=lambda: self._update_done.done.emit(update_in_place() or ""), daemon=True).start()

    def _on_updated(self, version):
        if version:
            self.updated.setText(f"Auto Clicker {version} is downloaded and checked. It starts the next time you open Auto Clicker.")
            self.updated.show()

    def _on_works_with(self, html):
        self.works.setText(html)
        self.works.show()

    def _set_status(self):
        running = bool(self.runner and self.runner.isRunning())
        name = self.config.hotkey["name"]
        what = "sequence" if self.tabs.currentIndex() == 1 else "clicking"
        self._show(f"Running {what} · {name} to stop" if running
                   else f"Idle · press {name} anywhere to start")

    # -- hotkey ------------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        winapi.apply_acrylic(int(self.winId()))
        self._register()

    def closeEvent(self, event):
        if self.runner and self.runner.isRunning():
            self.runner.stop()
            self.runner.wait(2000)
        winapi.unregister_hotkey(int(self.winId()), HOTKEY_ID)
        self.config.save()
        super().closeEvent(event)

    def _register(self):
        hotkey = self.config.hotkey
        if not winapi.register_hotkey(int(self.winId()), HOTKEY_ID,
                                      hotkey["mods"], hotkey["vk"]):
            link = 'style="color: rgba(232,234,237,0.8);"'
            self.status.setText(f"{hotkey['name']} is taken by another app · "
                                f'<a {link} href="#">See who holds it</a>')
            return False
        return True

    def _see_who_holds(self, _href):
        """HotkeyScan --check names the app holding the hotkey; without HotkeyScan, its page."""
        card = read_card("hotkeyscan")
        commands = card.get("commands") if card else None
        check = commands.get("check") if isinstance(commands, dict) else None
        if isinstance(check, list):
            combo = hotkeyscan_combo(self.config.hotkey)
            try:
                subprocess.Popen([card["exe"]] + [str(a).replace("{combo}", combo) for a in check])
                return
            except OSError:
                pass
        QDesktopServices.openUrl(QUrl("https://protagonistlabs.app/hotkeyscan/?utm_source=autoclicker"
                                      "&utm_medium=app&utm_campaign=hotkey-taken"))

    def _capture_hotkey(self, checked):
        self.hotkey_btn.setText("Press a key…" if checked else self.config.hotkey["name"])
        if checked:
            self.hotkey_btn.setFocus()

    def _hotkey_key(self, event):
        if not self.hotkey_btn.isChecked():
            return
        key = event.key()
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return
        if key == Qt.Key_Escape:
            self.hotkey_btn.setChecked(False)
            self._capture_hotkey(False)
            return

        modifiers = event.modifiers()
        mods, parts = 0, []
        for qt_mod, win_mod, name in (
                (Qt.ControlModifier, winapi.MOD_CONTROL, "Ctrl"),
                (Qt.AltModifier, winapi.MOD_ALT, "Alt"),
                (Qt.ShiftModifier, winapi.MOD_SHIFT, "Shift"),
                (Qt.MetaModifier, winapi.MOD_WIN, "Win")):
            if modifiers & qt_mod:
                mods |= win_mod
                parts.append(name)
        parts.append(QKeySequence(key).toString())

        previous = dict(self.config.hotkey)
        self.config.data["hotkey"] = {"mods": mods, "vk": event.nativeVirtualKey(),
                                      "name": "+".join(parts)}
        self.hotkey_btn.setChecked(False)
        self._capture_hotkey(False)
        if self._register():
            self.config.save()
            self._set_status()
        else:
            self.config.data["hotkey"] = previous
            self._register()
        self.hotkey_btn.setText(self.config.hotkey["name"])

    # -- frameless window plumbing ----------------------------------------
    def paintEvent(self, event):
        # A layered window passes the mouse straight through pixels with alpha 0,
        # so the window has to paint a body of its own - an unpainted title bar
        # clicks whatever is behind the window. The fill stays faint so the
        # acrylic underneath still reads as glass.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(24, 26, 30, 34))
        painter.setPen(QPen(QColor(255, 255, 255, 26), 1))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)

    def _start_drag(self, event):
        if event.button() == Qt.LeftButton:
            self.windowHandle().startSystemMove()

    def nativeEvent(self, event_type, message):
        if event_type != b"windows_generic_MSG":
            return False, 0
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == winapi.WM_HOTKEY and msg.wParam == HOTKEY_ID:
            self.toggle()
        elif msg.message == WM_NCHITTEST:
            # Frameless windows get no resize borders of their own.
            x = ctypes.c_short(msg.lParam & 0xFFFF).value
            y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
            rect = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(wintypes.HWND(int(self.winId())),
                                               ctypes.byref(rect))
            edge = int(BORDER * self.devicePixelRatioF())
            zone = (y - rect.top < edge, rect.bottom - y < edge,
                    x - rect.left < edge, rect.right - x < edge)
            code = HIT_CODES.get(zone)
            if code:
                return True, code
        return False, 0


def icon():
    """app.ico, whether running from source or from the one-file exe (PyInstaller unpacks
    --add-data next to the script into sys._MEIPASS)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "app.ico")
    return QIcon(path) if os.path.exists(path) else QIcon()


def main():
    app = QApplication(sys.argv)
    # Without an explicit AppUserModelID the taskbar groups the window under the interpreter
    # and shows its icon instead of ours.
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("limburatorul.AutoClicker")
    app.setWindowIcon(icon())
    app.setStyle("Fusion")
    palette = app.palette()
    palette.setColor(QPalette.Text, QColor("#E8EAED"))
    palette.setColor(QPalette.ButtonText, QColor("#E8EAED"))
    palette.setColor(QPalette.Window, QColor("#17191D"))
    palette.setColor(QPalette.Base, QColor("#1B1E23"))
    palette.setColor(QPalette.WindowText, QColor("#E8EAED"))
    app.setPalette(palette)
    app.setStyleSheet(theme.QSS)  # app-level: popups (combo lists, menus) are
                                  # separate top-level windows, outside a
                                  # widget-level stylesheet's reach
    window = AutoClicker()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
