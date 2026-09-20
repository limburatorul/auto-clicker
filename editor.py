"""Screen pickers, the step dialog and the sequence tree.

The nested step list is the single source of truth; the tree is rebuilt from it
after every change rather than kept in sync, which is what keeps moving a step
in and out of a loop from drifting out of step with the model.
"""

import time

import cv2
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QSpinBox, QStackedWidget,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

import engine
import store
import winapi

BRANCH_TITLES = {"steps": "Do", "then": "Then", "otherwise": "Else"}


# --- full screen pickers --------------------------------------------------

class ScreenPicker(QWidget):
    """Covers every monitor. Physical coordinates come from GetCursorPos, so no
    logical-to-physical DPI conversion is needed anywhere in here."""

    # (x, y) or (x, y, w, h) in physical pixels, or None if the user backed out.
    # Emitted exactly once, after the picker is gone, however it ended - callers
    # that hid their own windows to make room for it rely on always hearing back.
    finished = Signal(object)

    def __init__(self, region=False):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.region = region
        self.origin_logical = None
        self.origin_physical = None
        self.current_logical = None
        self._done = False
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

        bounds = QRect()
        for screen in QGuiApplication.screens():
            bounds = bounds.united(screen.geometry())
        self.setGeometry(bounds)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        if self.region and self.origin_logical and self.current_logical:
            box = QRect(self.origin_logical, self.current_logical).normalized()
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(box, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(91, 157, 255), 2))
            painter.drawRect(box)

        x, y = winapi.cursor_pos()
        label = f"{x}, {y}" + ("   drag a box · Esc cancels" if self.region
                               else "   click to pick · Esc cancels")
        painter.setPen(QPen(QColor(255, 255, 255, 230)))
        spot = self.mapFromGlobal(QGuiApplication.primaryScreen().availableGeometry().topLeft())
        cursor = self.current_logical or spot
        painter.fillRect(QRect(cursor + QPoint(14, 14), QPoint(cursor.x() + 250, cursor.y() + 40)),
                         QColor(20, 22, 26, 220))
        painter.drawText(cursor + QPoint(22, 36), label)

    def mouseMoveEvent(self, event):
        self.current_logical = event.position().toPoint()
        self.update()

    def _finish(self, result):
        if self._done:
            return
        self._done = True
        self.close()  # first, so the overlay is gone before anyone reads the screen
        self.finished.emit(result)

    def closeEvent(self, event):
        if not self._done:  # closed some other way, e.g. Alt+F4
            self._done = True
            self.finished.emit(None)
        super().closeEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if not self.region:
            self._finish(winapi.cursor_pos())
            return
        self.origin_logical = event.position().toPoint()
        self.origin_physical = winapi.cursor_pos()

    def mouseReleaseEvent(self, event):
        if not self.region or self.origin_physical is None:
            return
        end = winapi.cursor_pos()
        x, y = min(self.origin_physical[0], end[0]), min(self.origin_physical[1], end[1])
        width = abs(end[0] - self.origin_physical[0])
        height = abs(end[1] - self.origin_physical[1])
        self._finish((x, y, width, height) if width >= 4 and height >= 4 else None)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._finish(None)


def pick_point(on_done):
    """on_done gets (x, y), or None if the user backed out."""
    picker = ScreenPicker(region=False)
    picker.finished.connect(on_done)
    picker.showFullScreen()
    pick_point._keep = picker  # a local would be collected the moment we return


def capture_template(on_done):
    """Snip a region and keep it as the image to look for. on_done gets the
    saved file's path, or None if the user backed out."""
    def save(rect):
        if rect is None:
            on_done(None)
            return
        frame = winapi.grab_screen(rect)
        folder = store.APP_DIR / "images"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"target-{int(time.time())}.png"
        cv2.imwrite(str(path), frame)
        on_done(str(path))

    picker = ScreenPicker(region=True)
    picker.finished.connect(save)
    picker.showFullScreen()
    capture_template._keep = picker


# --- step dialog ----------------------------------------------------------

class StepDialog(QDialog):
    ORDER = ["click", "move", "delay", "loop", "wait_image", "if_image", "if_pixel"]

    def __init__(self, step=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Step")
        self.setMinimumWidth(360)
        step = step or {"type": "click", "target": "cursor", "button": "left", "count": 1}

        self.kind = QComboBox()
        for name in self.ORDER:
            self.kind.addItem(engine.STEP_LABELS[name], name)
        self.kind.setCurrentIndex(self.ORDER.index(step.get("type", "click")))

        self.pages = QStackedWidget()
        self.builders = {}
        for name in self.ORDER:
            page = QWidget()
            form = QFormLayout(page)
            form.setContentsMargins(0, 8, 0, 0)
            self.builders[name] = getattr(self, "_page_" + name)(form)
            self.pages.addWidget(page)
        self.pages.setCurrentIndex(self.ORDER.index(step.get("type", "click")))
        self.kind.currentIndexChanged.connect(self.pages.setCurrentIndex)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.kind)
        layout.addWidget(self.pages)
        layout.addWidget(buttons)

        self._load(step)

    # -- pages: each returns a dict of widgets
    def _spin(self, low, high, value, suffix=""):
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        if suffix:
            spin.setSuffix(suffix)
        return spin

    def _point_row(self, widgets, with_colour=False):
        widgets["x"] = self._spin(-32000, 32000, 0)
        widgets["y"] = self._spin(-32000, 32000, 0)
        pick = QPushButton("Pick point & colour" if with_colour else "Pick on screen",
                           objectName="plainBtn")
        pick.clicked.connect(lambda: self._pick_into(widgets, with_colour))
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.addWidget(widgets["x"])
        line.addWidget(widgets["y"])
        line.addWidget(pick)
        return row

    def _step_aside(self, pick, apply):
        """Hide this dialog and the window under it, so neither is in the way of
        (or in) what gets picked, and bring both back afterwards - also when the
        user backs out, which passes None and skips `apply`.

        Callers must open() this dialog, never exec() it: hiding a dialog that is
        inside exec() ends that call with Rejected, and the step being added was
        silently thrown away."""
        main = self.parentWidget()
        self.hide()
        main.hide()

        def back(result):
            if result is not None:
                apply(result)  # before our windows return, so they can't cover it
            main.show()
            self.open()

        pick(back)

    def _pick_into(self, widgets, with_colour=False):
        def apply(point):
            widgets["x"].setValue(point[0])
            widgets["y"].setValue(point[1])
            if with_colour:
                red, green, blue = winapi.pixel_color(point[0], point[1])
                widgets["color"].setText(f"#{red:02x}{green:02x}{blue:02x}")

        self._step_aside(pick_point, apply)

    def _image_row(self, widgets):
        widgets["path"] = QLineEdit()
        widgets["path"].setPlaceholderText("PNG to look for on screen")
        browse = QPushButton("Browse", objectName="plainBtn")
        browse.clicked.connect(lambda: self._browse_into(widgets))
        snip = QPushButton("Capture", objectName="plainBtn")
        snip.clicked.connect(lambda: self._snip_into(widgets))
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.addWidget(widgets["path"])
        line.addWidget(browse)
        line.addWidget(snip)
        return row

    def _browse_into(self, widgets):
        path, _ = QFileDialog.getOpenFileName(self, "Image to find", "",
                                              "Images (*.png *.jpg *.bmp)")
        if path:
            widgets["path"].setText(path)

    def _snip_into(self, widgets):
        self._step_aside(capture_template, widgets["path"].setText)

    def _page_click(self, form):
        widgets = {}
        widgets["target"] = QComboBox()
        widgets["target"].addItem("Wherever the cursor is", "cursor")
        widgets["target"].addItem("A fixed point", "point")
        widgets["target"].addItem("On the last image found", "found")
        form.addRow("Click", widgets["target"])
        point_row = self._point_row(widgets)
        form.addRow("Point", point_row)
        widgets["button"] = QComboBox()
        for name in ("left", "right", "middle"):
            widgets["button"].addItem(name.capitalize(), name)
        form.addRow("Button", widgets["button"])
        widgets["count"] = self._spin(1, 1000, 1)
        form.addRow("Times", widgets["count"])
        widgets["target"].currentIndexChanged.connect(
            lambda index: point_row.setEnabled(index == 1))
        point_row.setEnabled(False)
        return widgets

    def _page_move(self, form):
        widgets = {}
        form.addRow("To", self._point_row(widgets))
        return widgets

    def _page_delay(self, form):
        widgets = {"min": self._spin(1, 600000, 100, " ms"),
                   "max": self._spin(1, 600000, 100, " ms")}
        form.addRow("At least", widgets["min"])
        form.addRow("At most", widgets["max"])
        form.addRow("", QLabel("Equal values mean a fixed delay.", objectName="hint"))
        return widgets

    def _page_loop(self, form):
        widgets = {"count": self._spin(0, 100000, 5)}
        form.addRow("Repeat", widgets["count"])
        form.addRow("", QLabel("0 repeats until you stop it.", objectName="hint"))
        return widgets

    def _page_wait_image(self, form):
        widgets = {}
        form.addRow("Image", self._image_row(widgets))
        widgets["confidence"] = self._spin(50, 100, 85, " %")
        form.addRow("Confidence", widgets["confidence"])
        widgets["timeout"] = self._spin(100, 600000, 10000, " ms")
        form.addRow("Give up after", widgets["timeout"])
        return widgets

    def _page_if_image(self, form):
        widgets = {}
        form.addRow("Image", self._image_row(widgets))
        widgets["confidence"] = self._spin(50, 100, 85, " %")
        form.addRow("Confidence", widgets["confidence"])
        widgets["found"] = QComboBox()
        widgets["found"].addItem("is on screen", True)
        widgets["found"].addItem("is not on screen", False)
        form.addRow("Run Then when it", widgets["found"])
        return widgets

    def _page_if_pixel(self, form):
        widgets = {"color": QLineEdit("#ffffff")}
        form.addRow("Pixel", self._point_row(widgets, with_colour=True))
        form.addRow("Colour", widgets["color"])
        widgets["tolerance"] = self._spin(0, 255, 10)
        form.addRow("Tolerance", widgets["tolerance"])
        widgets["equals"] = QComboBox()
        widgets["equals"].addItem("matches", True)
        widgets["equals"].addItem("does not match", False)
        form.addRow("Run Then when it", widgets["equals"])
        return widgets

    # -- values
    def _load(self, step):
        widgets = self.builders[step.get("type", "click")]
        for key, widget in widgets.items():
            if key not in step:
                continue
            value = step[key]
            if isinstance(widget, QSpinBox):
                widget.setValue(int(value * 100) if key == "confidence" else int(value))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QComboBox):
                index = widget.findData(value)
                if index >= 0:
                    widget.setCurrentIndex(index)
        if step.get("type") == "click":
            widgets["target"].currentIndexChanged.emit(widgets["target"].currentIndex())

    def step(self):
        kind = self.kind.currentData()
        result = {"type": kind}
        for key, widget in self.builders[kind].items():
            if isinstance(widget, QSpinBox):
                result[key] = widget.value() / 100 if key == "confidence" else widget.value()
            elif isinstance(widget, QLineEdit):
                result[key] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                result[key] = widget.currentData()
        for key in engine.children_keys(result):
            result[key] = []
        return result


# --- the tree -------------------------------------------------------------

class SequenceEditor(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps = []

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.itemDoubleClicked.connect(lambda *_: self.edit())

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        for label, slot in (("Add", self.add), ("Edit", self.edit),
                            ("Duplicate", self.duplicate), ("Delete", self.delete)):
            button = QPushButton(label, objectName="plainBtn")
            button.clicked.connect(slot)
            buttons.addWidget(button)
        for label, slot in (("▲", self.move_up), ("▼", self.move_down)):
            # #stepBtn's narrow-square recipe, not #plainBtn's text padding -
            # 14px of horizontal padding squeezed a fixed-width glyph button
            # down to a sliver.
            button = QPushButton(label, objectName="stepBtn")
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.tree)
        layout.addLayout(buttons)

    # -- model <-> tree
    def set_steps(self, steps):
        self.steps = steps
        self.rebuild()

    def rebuild(self):
        self.tree.clear()
        self._fill(self.tree.invisibleRootItem(), self.steps, [])

    def _fill(self, parent, steps, path):
        for index, step in enumerate(steps):
            item = QTreeWidgetItem(parent, [engine.describe(step)])
            item.setData(0, Qt.UserRole, path + [index])
            item.setForeground(0, QColor("#E8EAED"))
            for key in engine.children_keys(step):
                branch = QTreeWidgetItem(item, [BRANCH_TITLES.get(key, key)])
                branch.setData(0, Qt.UserRole, path + [index, key])
                branch.setForeground(0, QColor(232, 234, 237, 140))
                self._fill(branch, step.setdefault(key, []), path + [index, key])
                branch.setExpanded(True)
            item.setExpanded(True)

    def _container(self, path):
        """Walk index/key pairs down to the list a path lives in."""
        container = self.steps
        position = 0
        while position < len(path) - 1:
            container = container[path[position]].setdefault(path[position + 1], [])
            position += 2
        return container

    def _selected_path(self):
        item = self.tree.currentItem()
        return list(item.data(0, Qt.UserRole)) if item else None

    def _select(self, path):
        def walk(item):
            for row in range(item.childCount()):
                child = item.child(row)
                if list(child.data(0, Qt.UserRole) or []) == path:
                    self.tree.setCurrentItem(child)
                    return True
                if walk(child):
                    return True
            return False

        walk(self.tree.invisibleRootItem())

    # -- actions
    def _open(self, dialog, on_accepted):
        # open(), not exec(): see StepDialog._step_aside
        dialog.accepted.connect(lambda: on_accepted(dialog.step()))
        dialog.finished.connect(dialog.deleteLater)
        dialog.open()

    def add(self):
        self._open(StepDialog(parent=self.window()), self._insert)

    def _insert(self, step):
        path = self._selected_path()
        if path is None:
            self.steps.append(step)
            target = [len(self.steps) - 1]
        elif isinstance(path[-1], str):          # a Then/Else/Do header
            container = self._container(path + [0])
            container.append(step)
            target = path + [len(container) - 1]
        else:
            container = self._container(path)
            container.insert(path[-1] + 1, step)
            target = path[:-1] + [path[-1] + 1]
        self.rebuild()
        self._select(target)
        self.changed.emit()

    def edit(self):
        path = self._selected_path()
        if not path or isinstance(path[-1], str):
            return
        container = self._container(path)
        current = container[path[-1]]

        def replace(updated):
            for key in engine.children_keys(updated):      # keep nested steps on edit
                if key in current:
                    updated[key] = current[key]
            container[path[-1]] = updated
            self.rebuild()
            self._select(path)
            self.changed.emit()

        self._open(StepDialog(current, parent=self.window()), replace)

    def duplicate(self):
        path = self._selected_path()
        if not path or isinstance(path[-1], str):
            return
        import copy
        container = self._container(path)
        container.insert(path[-1] + 1, copy.deepcopy(container[path[-1]]))
        self.rebuild()
        self.changed.emit()

    def delete(self):
        path = self._selected_path()
        if not path or isinstance(path[-1], str):
            return
        container = self._container(path)
        del container[path[-1]]
        self.rebuild()
        self.changed.emit()

    def _move(self, offset):
        path = self._selected_path()
        if not path or isinstance(path[-1], str):
            return
        container = self._container(path)
        index = path[-1]
        target = index + offset
        if not 0 <= target < len(container):
            return
        container[index], container[target] = container[target], container[index]
        self.rebuild()
        self._select(path[:-1] + [target])
        self.changed.emit()

    def move_up(self):
        self._move(-1)

    def move_down(self):
        self._move(1)

    # -- files
    def save_to_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save sequence", "sequence.json",
                                              "Sequence (*.json)")
        if path:
            store.export_steps(path, self.steps)

    def load_from_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load sequence", "", "Sequence (*.json)")
        if not path:
            return
        try:
            steps = store.import_steps(path)
        except ValueError as error:
            QMessageBox.warning(self, "Load sequence", str(error))
            return
        self.steps[:] = steps
        self.rebuild()
        self.changed.emit()
