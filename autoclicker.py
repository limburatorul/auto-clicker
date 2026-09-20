"""Auto Clicker - clicks where the cursor is, or runs a sequence you built."""

import ctypes
import os
import sys
from ctypes import wintypes

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (QColor, QIcon, QKeySequence, QPainter, QPalette,
                           QPen)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
                               QHBoxLayout, QInputDialog, QLabel, QListWidget,
                               QMenu, QMessageBox, QPushButton, QSpinBox,
                               QTabWidget, QVBoxLayout, QWidget)

import editor
import engine
import store
import theme
import winapi

HOTKEY_ID = 1
WM_NCHITTEST = 0x0084
BORDER = 6
HIT_CODES = {(True, False, True, False): 13, (True, False, False, True): 14,
             (False, True, True, False): 16, (False, True, False, True): 17,
             (True, False, False, False): 12, (False, True, False, False): 15,
             (False, False, True, False): 10, (False, False, False, True): 11}


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
        body.addWidget(self.status)

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

        self.interval_min = QSpinBox()
        self.interval_min.setRange(1, 600000)
        self.interval_min.setSingleStep(10)
        self.interval_min.setSuffix(" ms")
        self.interval_min.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.interval_min.setButtonSymbols(QSpinBox.NoButtons)
        self.interval_min.setFixedWidth(88)
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
        self.interval_max = QSpinBox()
        self.interval_max.setRange(1, 600000)
        self.interval_max.setSingleStep(10)
        self.interval_max.setSuffix(" ms")
        self.interval_max.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.interval_max.setButtonSymbols(QSpinBox.NoButtons)
        self.interval_max.setFixedWidth(88)
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
        if self.target.currentData() != "points":
            self.target.setCurrentIndex(1)  # picking a point implies using the list
        self.hide()

        def done(point):
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

        self.runner = engine.Runner(steps, repeat)
        self.runner.counted.connect(self._on_count)
        self.runner.note.connect(self.status.setText)
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
        self.status.setText(f"Running · {count} clicks · {self.config.hotkey['name']} to stop")

    def _on_stopped(self):
        self._set_running(False)

    def _set_status(self):
        running = bool(self.runner and self.runner.isRunning())
        name = self.config.hotkey["name"]
        what = "sequence" if self.tabs.currentIndex() == 1 else "clicking"
        self.status.setText(f"Running {what} · {name} to stop" if running
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
            self.status.setText(f"{hotkey['name']} is taken by another app")
            return False
        return True

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
