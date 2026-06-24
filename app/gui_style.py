"""Styl (QSS) i ikony GUI — bez zależności od klas Qt (same stałe)."""
from __future__ import annotations

ICON = {"image": "🖼", "video": "🎬"}

APP_STYLE = """
* { font-family: "Inter", "Ubuntu", "Segoe UI", sans-serif; }

QWidget { background-color: #0f1622; color: #e7ebf3; font-size: 13px; }

QLabel#Title { font-size: 22px; font-weight: 700; color: #f2f5fa; }
QLabel#Subtitle { font-size: 13px; color: #8a96ab; }

QFrame#Card, QGroupBox {
    background-color: #161f30; border: 1px solid #283248; border-radius: 14px;
}
QGroupBox {
    margin-top: 16px; padding: 18px 14px 14px 14px; font-weight: 600; color: #e7ebf3;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 16px; top: 4px; padding: 0 6px; color: #8a96ab; font-weight: 600; font-size: 12px;
}

QListWidget, QLineEdit, QComboBox, QPlainTextEdit {
    background-color: #121a29; border: 1px solid #283248; border-radius: 10px;
    padding: 8px; color: #e7ebf3; selection-background-color: #1c3a32; selection-color: #d8fff0;
}
QListWidget[empty="true"] { border: 2px dashed #34495f; color: #5d6b80; }
QListWidget::item { padding: 4px 2px; border-radius: 6px; }
QListWidget::item:selected { background-color: #1c3a32; color: #d8fff0; }

QPushButton { border: none; border-radius: 9px; padding: 9px 20px; font-weight: 600; }
QPushButton#Primary { background-color: #34d399; color: #07291d; }
QPushButton#Primary:hover   { background-color: #4ee0ac; }
QPushButton#Primary:pressed { background-color: #22b67f; }
QPushButton#Primary:disabled { background-color: #283248; color: #5d6b80; }
QPushButton#Secondary {
    background-color: #1c2638; color: #e7ebf3; border: 1px solid #2c3850;
}
QPushButton#Secondary:hover   { background-color: #243049; }
QPushButton#Secondary:pressed { background-color: #1a2336; }

QRadioButton, QCheckBox { spacing: 10px; padding: 3px 0; color: #e7ebf3; }
QRadioButton::indicator, QCheckBox::indicator {
    width: 17px; height: 17px; border-radius: 9px; border: 1.5px solid #3b4863; background: #121a29;
}
QRadioButton::indicator:checked { border: 5px solid #34d399; background: #121a29; }
QCheckBox::indicator { border-radius: 5px; }
QCheckBox::indicator:checked { border: 1.5px solid #34d399; background: #34d399; }

QProgressBar {
    border: none; border-radius: 6px; background-color: #1c2638; height: 10px;
    text-align: center; color: transparent;
}
QProgressBar::chunk { background-color: #34d399; border-radius: 6px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #2c3850; border-radius: 5px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #3b4a68; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
