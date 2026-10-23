"""What's new, as the studio's other apps show it: every release on the left under the month it came out,
the chosen one on the right under its 960 x 170 banner. The notes are whatsnew.txt, built into the exe,
so it works offline and shows every release. It opens once after an update (seen when it is closed, not
when it opens) and from the What's new link under the Start button."""

import ctypes
import html
import os
import random
import re
import sys
from datetime import date
from ctypes import wintypes

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
                               QVBoxLayout, QWidget)

# Auto Clicker's colours in the studio's banner template (Marketing\banners\banner.html)
GOLD, PALE, GROUND1, GROUND2 = QColor("#ffc533"), QColor("#fff0a0"), QColor("#17140a"), QColor("#221c0c")


def releases():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    found = []
    with open(os.path.join(base, "whatsnew.txt"), encoding="utf-8") as f:
        for line in f.read().splitlines():
            head = re.match(r"## (\S+) \| (\d{4}-\d\d-\d\d) \| (.+)", line)
            if head:
                found.append({"version": head[1], "date": date.fromisoformat(head[2]), "title": head[3], "lines": []})
            elif found and line.strip() and not line.startswith("#"):
                found[-1]["lines"].append(line.strip())
    return found


def _rich(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return re.sub(r"`(.+?)`", r"<span style='font-family: Consolas'>\1</span>", text)


class Banner(QWidget):
    """960 x 170, smaller with the window but never taller than its width allows. Drawn in Auto Clicker's
    colours: click ripples and pointers placed by a generator seeded with the version, so a release looks
    the same every time and its neighbours never look alike."""

    def __init__(self):
        super().__init__()
        self.release = None
        policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMaximumWidth(960)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return round(min(width, 960) * 170 / 960)

    def resizeEvent(self, event):
        self.setFixedHeight(self.heightForWidth(self.width()))

    def paintEvent(self, event):
        if not self.release:
            return
        r = self.release
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), 10, 10)
        p.setClipPath(clip)
        p.scale(self.width() / 960, self.height() / 170)
        ground = QLinearGradient(0, 0, 960, 170)
        ground.setColorAt(0, GROUND1)
        ground.setColorAt(0.55, GROUND2)
        ground.setColorAt(1, QColor("#0d0d16"))
        p.fillRect(QRectF(0, 0, 960, 170), ground)
        rnd = random.Random(r["version"])
        glow = QRadialGradient(QPointF(620 + rnd.random() * 200, 30), 320)
        glow.setColorAt(0, QColor(255, 197, 51, 100))
        glow.setColorAt(1, QColor(255, 197, 51, 0))
        p.fillRect(QRectF(0, 0, 960, 170), glow)
        for _ in range(4 + int(rnd.random() * 3)):
            x, y = 470 + rnd.random() * 450, 20 + rnd.random() * 130
            for ring in range(3):
                colour = QColor(PALE if ring == 0 else GOLD)
                colour.setAlpha(170 - ring * 50)
                p.setPen(QPen(colour, 2))
                p.setBrush(Qt.NoBrush)
                radius = 8 + ring * 12 + rnd.random() * 4
                p.drawEllipse(QPointF(x, y), radius, radius)
            arrow = QPainterPath()
            arrow.moveTo(x + 2, y + 2)
            for dx, dy in ((2, 26), (9, 19), (15, 31), (20, 29), (14, 17), (24, 17)):
                arrow.lineTo(x + dx, y + dy)
            arrow.closeSubpath()
            p.setPen(QPen(QColor(0, 0, 0, 160), 1.5))
            p.setBrush(QColor(255, 255, 255, 235))
            p.drawPath(arrow)
        p.setPen(QColor(255, 255, 255, 205))
        p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        p.drawText(QPointF(26, 58), "WHAT’S NEW IN AUTO CLICKER")
        p.setPen(PALE)
        p.setFont(QFont("Segoe UI", 28, QFont.Bold))
        p.drawText(QPointF(23, 104), r["version"])
        p.setPen(QColor(255, 255, 255, 230))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRectF(26, 116, 430, 44), Qt.TextWordWrap, r["title"])


class WhatsNew(QDialog):
    _open = None

    @classmethod
    def show_once(cls, parent, config, version, ran_before):
        """After an update only: a first install has nothing new to tell. Before 1.1.0 nothing was
        written down, so a config that was already there means an update."""
        seen = config.data.get("whatsnew_seen")
        if seen == version:
            return
        if seen is not None or ran_before:
            cls.open(parent, config, version)
        else:
            config.data["whatsnew_seen"] = version
            config.save()

    @classmethod
    def open(cls, parent, config, version):
        if cls._open:
            cls._open.raise_()
            cls._open.activateWindow()
            return
        cls._open = WhatsNew(parent, config, version)
        cls._open.show()

    def __init__(self, parent, config, version):
        # A window of its own, but the main window's: closing Auto Clicker closes it too (and does not
        # count as seen, so it comes back at the next start).
        super().__init__(parent, Qt.Window)
        self.config, self.version = config, version
        self.setWindowTitle("What's new — Auto Clicker")
        self.finished.connect(self._closed)
        self.resize(1240, 720)
        self.setMinimumSize(700, 420)
        self.releases = releases()
        self.shown = -1

        self.nav = QVBoxLayout()
        self.nav.setSpacing(1)
        self.buttons = []
        month = None
        for i, r in enumerate(self.releases):
            m = r["date"].strftime("%B %Y")
            if m != month:
                month = m
                heading = QLabel(m, objectName="hint")
                heading.setContentsMargins(8, 0 if i == 0 else 12, 0, 4)
                self.nav.addWidget(heading)
            button = QPushButton(objectName="wnRow")
            button.setAccessibleName(f"{r['version']}, {r['title']}")
            button.setToolTip(r["title"])
            row = QHBoxLayout(button)
            row.setContentsMargins(8, 0, 8, 0)
            row.addWidget(QLabel(r["version"]))
            row.addStretch()
            row.addWidget(QLabel("Latest" if i == 0 else r["date"].strftime("%d %b").lstrip("0"), objectName="hint"))
            button.clicked.connect(lambda _=False, i=i: self.show_release(i))
            self.buttons.append(button)
            self.nav.addWidget(button)
        self.nav.addStretch()
        nav_box = QWidget()
        nav_box.setLayout(self.nav)
        nav_scroll = QScrollArea(widgetResizable=True, frameShape=QScrollArea.NoFrame)
        nav_scroll.setWidget(nav_box)
        nav_scroll.setFixedWidth(200)

        self.banner = Banner()
        self.notes = QLabel(wordWrap=True, textFormat=Qt.RichText, alignment=Qt.AlignTop | Qt.AlignLeft)
        self.notes.setTextInteractionFlags(Qt.TextSelectableByMouse)
        notes_scroll = QScrollArea(widgetResizable=True, frameShape=QScrollArea.NoFrame)
        notes_scroll.setWidget(self.notes)
        self.notes_scroll = notes_scroll
        right = QVBoxLayout()
        right.setSpacing(14)
        right.addWidget(self.banner)
        right.addWidget(notes_scroll, 1)

        body = QHBoxLayout()
        body.setSpacing(16)
        body.addWidget(nav_scroll)
        body.addLayout(right, 1)
        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(self.close)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(close)
        page = QVBoxLayout(self)
        page.setContentsMargins(18, 16, 18, 14)
        page.addLayout(body, 1)
        page.addLayout(bottom)
        self.setStyleSheet("""
            QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }
            QPushButton#wnRow { background: transparent; border: 1px solid transparent; border-radius: 8px;
                                padding: 0px; min-height: 34px; max-height: 34px; text-align: left; }
            QPushButton#wnRow:hover { background: rgba(255,255,255,0.06); }
            QPushButton#wnRow[current="true"] { background: rgba(255,197,51,0.16); border: 1px solid rgba(255,197,51,0.35); }
            QPushButton#wnRow:focus { border: 1px solid rgba(255,197,51,0.8); }
            #hint { font-size: 11px; }
        """)
        current = next((i for i, r in enumerate(self.releases) if r["version"] == version), 0)
        self.show_release(current)

    def show_release(self, i):
        if not 0 <= i < len(self.releases) or i == self.shown:
            return
        self.shown = i
        r = self.releases[i]
        for j, button in enumerate(self.buttons):
            button.setProperty("current", "true" if j == i else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        self.banner.release = r
        self.banner.update()
        points = "".join(f"<li style='margin-bottom: 6px'>{_rich(line[2:])}</li>" for line in r["lines"] if line.startswith("- "))
        self.notes.setText(f"<p style='color: rgba(232,234,237,0.55)'>{r['date'].day} {r['date']:%B %Y}</p><ul style='margin-left: -20px; font-size: 13px; line-height: 140%'>{points}</ul>")
        self.notes_scroll.verticalScrollBar().setValue(0)

    def showEvent(self, event):
        super().showEvent(event)
        # a dark title bar, like the window it came from (DWMWA_USE_IMMERSIVE_DARK_MODE)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(int(self.winId())), 20,
                                                   ctypes.byref(ctypes.c_int(1)), 4)
        self.buttons[self.shown].setFocus()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Down, Qt.Key_Up):
            self.show_release(max(0, min(len(self.releases) - 1, self.shown + (1 if event.key() == Qt.Key_Down else -1))))
            self.buttons[self.shown].setFocus()
            return
        super().keyPressEvent(event)  # Esc closes: finished

    def _closed(self):
        """Esc, Close or the title bar's X: seen now, not when it opened."""
        self.config.data["whatsnew_seen"] = self.version
        self.config.save()
        WhatsNew._open = None
        self.deleteLater()
