"""One stylesheet for the whole app - native controls are styled here, once,
not per widget. Menus and popups stay opaque: on glass they are unreadable."""

QSS = """
#titleBar { background: transparent; }
#title { color: #E8EAED; font-size: 12px; font-weight: 600; }
QPushButton#winBtn, QPushButton#closeBtn {
    background: transparent; border: none; color: rgba(232,234,237,0.6);
    font-size: 13px; border-radius: 6px; min-width: 30px; max-width: 30px;
    min-height: 26px; max-height: 26px;
}
QPushButton#winBtn:hover { background: rgba(255,255,255,0.10); color: #E8EAED; }
QPushButton#closeBtn:hover { background: rgba(232,72,72,0.85); color: #FFFFFF; }

QLabel { color: #E8EAED; font-size: 12px; }
#cardLabel { color: rgba(232,234,237,0.62); font-size: 10px;
             font-weight: 600; letter-spacing: 1px; }
#status { color: rgba(232,234,237,0.55); font-size: 11px; }
#hint { color: rgba(232,234,237,0.45); font-size: 10px; }

QFrame#card {
    background: rgba(255,255,255,0.055);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 12px;
}
QFrame#card[locked="true"] { background: rgba(255,255,255,0.03); }

QTabWidget::pane { border: none; }
QTabBar::tab {
    background: transparent; color: rgba(232,234,237,0.55);
    padding: 7px 14px; margin-right: 4px; border-radius: 9px;
    font-size: 11px; font-weight: 600;
}
QTabBar::tab:hover { background: rgba(255,255,255,0.07); color: #E8EAED; }
QTabBar::tab:selected { background: rgba(255,255,255,0.12); color: #E8EAED; }

QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {
    background: rgba(0,0,0,0.28);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px; padding: 5px 8px; color: #E8EAED; font-size: 12px;
    selection-background-color: rgba(91,157,255,0.45);
}
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus {
    border: 1px solid rgba(91,157,255,0.75);
}
QSpinBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled, QComboBox:disabled {
    color: rgba(232,234,237,0.30); background: rgba(0,0,0,0.16);
}
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background: #1B1E23; border: 1px solid rgba(255,255,255,0.14);
    color: #E8EAED; selection-background-color: rgba(91,157,255,0.35);
    outline: none; padding: 4px;
}

QPushButton#stepBtn {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 8px; color: #E8EAED; font-size: 14px; font-weight: 700;
    min-width: 26px; max-width: 26px; min-height: 28px; max-height: 28px;
    padding-bottom: 2px;
}
QPushButton#stepBtn:hover { background: rgba(255,255,255,0.18); }
QPushButton#stepBtn:pressed { background: rgba(91,157,255,0.35); }
QPushButton#stepBtn:disabled { color: rgba(232,234,237,0.25);
                               background: rgba(255,255,255,0.03); }

/* Same lifted-surface recipe as #stepBtn: a light overlay, not a dark well -
   a button reads as something to press, an input field as something to fill. */
QPushButton#hotkeyBtn, QPushButton#plainBtn, QDialog QPushButton {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 8px; padding: 7px 14px; color: #E8EAED;
    font-size: 12px; font-weight: 600;
}
QPushButton#hotkeyBtn:hover, QPushButton#plainBtn:hover, QDialog QPushButton:hover {
    background: rgba(255,255,255,0.13); border: 1px solid rgba(255,255,255,0.22);
}
QPushButton#hotkeyBtn:pressed, QPushButton#plainBtn:pressed, QDialog QPushButton:pressed {
    background: rgba(255,255,255,0.04);
}
QPushButton#hotkeyBtn:disabled, QPushButton#plainBtn:disabled,
QDialog QPushButton:disabled {
    color: rgba(232,234,237,0.28); background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
}
QPushButton#hotkeyBtn:checked {
    border: 1px solid rgba(91,157,255,0.85);
    background: rgba(91,157,255,0.18); color: #9CC4FF;
}

QPushButton#toggleBtn {
    background: rgba(91,157,255,0.90); border: none; border-radius: 12px;
    color: #0C1524; font-size: 14px; font-weight: 700; padding: 13px;
}
QPushButton#toggleBtn:hover { background: rgba(120,177,255,0.95); }
QPushButton#toggleBtn:pressed { background: rgba(74,138,224,0.95); }
QPushButton#toggleBtn[running="true"] { background: rgba(232,88,88,0.90); color: #200C0C; }
QPushButton#toggleBtn[running="true"]:hover { background: rgba(240,110,110,0.95); }
QPushButton#toggleBtn[running="true"]:pressed { background: rgba(196,68,68,0.95); }

QCheckBox { color: #E8EAED; font-size: 12px; spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid rgba(255,255,255,0.22); background: rgba(0,0,0,0.28);
}
QCheckBox::indicator:checked {
    background: rgba(91,157,255,0.90); border: 1px solid rgba(91,157,255,0.9);
}
QCheckBox:disabled { color: rgba(232,234,237,0.30); }

QTreeWidget, QListWidget {
    background: rgba(0,0,0,0.22); border: 1px solid rgba(255,255,255,0.10);
    border-radius: 10px; color: #E8EAED; font-size: 12px;
    outline: none; padding: 4px;
}
QTreeWidget::item, QListWidget::item { padding: 4px 2px; border-radius: 6px; }
QTreeWidget::item:selected, QListWidget::item:selected {
    background: rgba(91,157,255,0.28);
}
QTreeWidget:disabled, QListWidget:disabled { color: rgba(232,234,237,0.30); }
QHeaderView::section { background: transparent; color: rgba(232,234,237,0.5);
                       border: none; padding: 4px; }

/* 10px track for the grab area, 6px of visible thumb inside it. Translucent
   white rather than a palette colour so it reads over glass too. */
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical {
    background: rgba(255,255,255,0.16); min-height: 28px; border-radius: 5px;
    border: 2px solid transparent; background-clip: padding-box;
}
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,0.30);
                                    background-clip: padding-box; }
QScrollBar::handle:vertical:pressed { background: rgba(255,255,255,0.42);
                                      background-clip: padding-box; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:horizontal {
    background: rgba(255,255,255,0.16); min-width: 28px; border-radius: 5px;
    border: 2px solid transparent; background-clip: padding-box;
}
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QDialog { background: #17191D; }
QDialog QLabel { color: #E8EAED; }
QMenu { background: #1B1E23; border: 1px solid rgba(255,255,255,0.14);
        color: #E8EAED; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 12px; border-radius: 6px; }
QMenu::item:selected { background: rgba(91,157,255,0.30); }
QToolTip { background: #1B1E23; color: #E8EAED;
           border: 1px solid rgba(255,255,255,0.16); padding: 4px; }
"""
