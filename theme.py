#!/usr/bin/env python3
# theme.py

BRAND_CYAN = "#00D4AA"
BRAND_CYAN_DIM = "#00A88A"
BRAND_DARK = "#0A0E14"
BRAND_PANEL = "#111820"
BRAND_CARD = "#161D27"
BRAND_BORDER = "#1E2A36"
BRAND_TEXT = "#E4EAF0"
BRAND_TEXT_SOFT = "#B8C4D0"
BRAND_TEXT_DIM = "#7A8B9C"
BRAND_ACCENT2 = "#FF6B35"
BRAND_WARN = "#FFB800"
BRAND_RED = "#FF4757"
BRAND_GREEN = "#2ED573"

FONT_MONO = "'JetBrains Mono', 'Consolas', 'Fira Code', monospace"
FONT_UI = "'Segoe UI', 'SF Pro Display', 'Helvetica Neue', sans-serif"

STYLESHEET = f"""
QWidget {{
    background-color: {BRAND_DARK};
    color: {BRAND_TEXT};
    font-family: {FONT_UI};
    font-size: 12px;
}}

QLabel {{
    background: transparent;
    border: none;
}}

QFrame#Panel {{
    background-color: {BRAND_PANEL};
    border-left: 1px solid {BRAND_BORDER};
}}

QFrame#Card {{
    background-color: {BRAND_CARD};
    border: 1px solid {BRAND_BORDER};
    border-radius: 12px;
}}

QPushButton {{
    background-color: transparent;
    border: 1px solid {BRAND_BORDER};
    border-radius: 6px;
    color: {BRAND_TEXT_SOFT};
    padding: 6px 14px;
    font-weight: bold;
    font-family: {FONT_MONO};
    font-size: 11px;
}}
QPushButton:hover {{
    border: 1px solid {BRAND_CYAN};
    color: {BRAND_CYAN};
}}
QPushButton:pressed {{
    background-color: rgba(0, 212, 170, 32);
}}

QPushButton#ChipActive {{
    background-color: rgba(0, 212, 170, 21);
    border: 1px solid {BRAND_CYAN};
    color: {BRAND_CYAN};
}}

QPushButton#OutlineBtn {{
    border: 1px solid rgba(0, 212, 170, 96);
    color: {BRAND_CYAN};
    background: rgba(0, 212, 170, 16);
    font-family: {FONT_MONO};
    font-size: 10px;
    padding: 3px 10px;
    border-radius: 5px;
}}
QPushButton#OutlineBtn:hover {{
    background: rgba(0, 212, 170, 32);
    border: 1px solid {BRAND_CYAN};
}}

QPushButton#GradientBtn {{
    background-color: rgba(0, 212, 170, 25);
    border: 1px solid rgba(0, 212, 170, 100);
    color: {BRAND_CYAN};
    border-radius: 8px;
    padding: 10px 0px;
    font-weight: 600;
    font-family: {FONT_MONO};
    font-size: 12px;
}}
QPushButton#GradientBtn:hover {{
    background-color: rgba(0, 212, 170, 50);
    border: 1px solid {BRAND_CYAN};
}}

QSlider::groove:horizontal {{
    border-radius: 2px;
    height: 4px;
    background: {BRAND_BORDER};
}}
QSlider::sub-page:horizontal {{
    background: {BRAND_CYAN};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {BRAND_CYAN};
    border: 2px solid #ffffff;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}

QSlider#WarnSlider::sub-page:horizontal {{
    background: {BRAND_WARN};
}}
QSlider#WarnSlider::handle:horizontal {{
    background: {BRAND_WARN};
    border: 2px solid #ffffff;
}}

QSlider#AccentSlider::sub-page:horizontal {{
    background: {BRAND_ACCENT2};
}}
QSlider#AccentSlider::handle:horizontal {{
    background: {BRAND_ACCENT2};
    border: 2px solid #ffffff;
}}

QComboBox {{
    background-color: {BRAND_CARD};
    border: 1px solid {BRAND_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {BRAND_TEXT};
    font-weight: bold;
    min-width: 200px;
    font-family: {FONT_MONO};
    font-size: 11px;
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: {BRAND_CARD};
    border: 1px solid {BRAND_BORDER};
    color: {BRAND_TEXT};
    selection-background-color: rgba(0, 212, 170, 48);
    selection-color: {BRAND_CYAN};
    padding: 4px;
}}

/* Tab styling — fix ghost box */
QTabWidget {{
    background: transparent;
}}
QTabWidget::pane {{
    border: none;
    background: transparent;
}}
QTabWidget::tab-bar {{
    background: transparent;
}}
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: {BRAND_TEXT_SOFT};
    padding: 14px 10px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 600;
    font-family: {FONT_MONO};
    font-size: 11px;
}}
QTabBar::tab:selected {{
    color: {BRAND_CYAN};
    border-bottom: 2px solid {BRAND_CYAN};
}}
QTabBar::tab:hover:!selected {{
    color: {BRAND_TEXT};
}}
QTabBar::tab:last {{
    border: none;
    border-bottom: 2px solid transparent;
}}

QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 6px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {BRAND_BORDER};
    min-height: 20px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(0, 212, 170, 128);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    border: none;
    background: none;
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 6px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: {BRAND_BORDER};
    min-width: 20px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal:hover {{
    background: rgba(0, 212, 170, 128);
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    border: none;
    background: none;
    width: 0px;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

QProgressBar {{
    background-color: {BRAND_BORDER};
    border: none;
    border-radius: 3px;
    max-height: 6px;
}}
QProgressBar::chunk {{
    background: {BRAND_CYAN};
    border-radius: 3px;
}}

QToolTip {{
    background-color: {BRAND_CARD};
    color: {BRAND_TEXT};
    border: 1px solid {BRAND_BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    font-family: {FONT_MONO};
    font-size: 11px;
}}
"""
