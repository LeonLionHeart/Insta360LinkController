#!/usr/bin/env python3
# ui_widgets.py

from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                             QSlider, QPushButton, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, pyqtProperty, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QBrush
import theme


class SliderWidget(QWidget):
    valueChanged = pyqtSignal(int)

    def __init__(self, label_text, min_val=0, max_val=100, default_val=50, unit="", is_warn=False, is_accent=False):
        super().__init__()
        self.unit = unit
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        self.lbl_name = QLabel(label_text.upper())
        self.lbl_name.setStyleSheet(
            f"color: {theme.BRAND_TEXT_SOFT}; font-size: 11px; font-weight: bold; "
            f"letter-spacing: 0.5px; font-family: {theme.FONT_MONO};"
        )
        self.lbl_val = QLabel(f"{default_val}{self.unit}")
        self.lbl_val.setStyleSheet(
            f"color: {theme.BRAND_TEXT}; font-weight: 600; "
            f"font-family: {theme.FONT_MONO}; font-size: 12px;"
        )
        header.addWidget(self.lbl_name)
        header.addStretch()
        header.addWidget(self.lbl_val)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(min_val)
        self.slider.setMaximum(max_val)
        self.slider.setValue(default_val)
        if is_warn:
            self.slider.setObjectName("WarnSlider")
        elif is_accent:
            self.slider.setObjectName("AccentSlider")
        self.slider.valueChanged.connect(self._on_value_changed)

        layout.addLayout(header)
        layout.addWidget(self.slider)

    def _on_value_changed(self, val):
        self.lbl_val.setText(f"{val}{self.unit}")
        self.valueChanged.emit(val)

    def set_value(self, val):
        self.slider.setValue(val)


class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, default_state=False):
        super().__init__()
        self.setFixedSize(40, 22)
        self._checked = default_state
        self._thumb_pos = 20 if self._checked else 2
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.animation = QPropertyAnimation(self, b"thumb_pos", self)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation.setDuration(150)

    @pyqtProperty(int)
    def thumb_pos(self):
        return self._thumb_pos

    @thumb_pos.setter
    def thumb_pos(self, pos):
        self._thumb_pos = pos
        self.update()

    def set_checked(self, state):
        if self._checked != state:
            self._checked = state
            self._thumb_pos = 20 if self._checked else 2
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self.toggled.emit(self._checked)
            self.animation.setEndValue(20 if self._checked else 2)
            self.animation.start()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        track_color = QColor(theme.BRAND_CYAN) if self._checked else QColor(theme.BRAND_BORDER)
        p.setBrush(QBrush(track_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, self.width(), self.height(), 11, 11)
        p.setBrush(QBrush(QColor("#FFFFFF")))
        p.drawEllipse(self._thumb_pos, 2, 18, 18)
        p.end()


class PresetChip(QPushButton):
    def __init__(self, label_text):
        super().__init__(label_text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumWidth(55)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {theme.BRAND_BORDER};
                border-radius: 6px;
                color: {theme.BRAND_TEXT_SOFT};
                padding: 6px 14px;
                font-weight: 600;
                font-family: {theme.FONT_MONO};
                font-size: 11px;
                letter-spacing: 0.5px;
            }}
            QPushButton:checked {{
                background: {theme.BRAND_CYAN}20;
                border: 1px solid {theme.BRAND_CYAN};
                color: {theme.BRAND_CYAN};
            }}
            QPushButton:hover:!checked {{
                border: 1px solid {theme.BRAND_TEXT_DIM};
                color: {theme.BRAND_TEXT};
            }}
        """)


class SectionHeader(QWidget):
    def __init__(self, icon, title, right_widget=None):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 14)
        lbl = QLabel(f"{icon}  {title.upper()}")
        lbl.setStyleSheet(
            f"color: {theme.BRAND_TEXT}; font-weight: 700; font-size: 13px; "
            f"letter-spacing: 0.8px; font-family: {theme.FONT_MONO};"
        )
        layout.addWidget(lbl)
        layout.addStretch()
        if right_widget:
            layout.addWidget(right_widget)


class Divider(QWidget):
    """Horizontal line separator."""
    def __init__(self):
        super().__init__()
        self.setFixedHeight(33)
        self._line = QFrame(self)
        self._line.setFixedHeight(1)
        self._line.setStyleSheet(f"background-color: {theme.BRAND_BORDER};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.addWidget(self._line)


class StatusDot(QWidget):
    """Pulsing status indicator dot."""
    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        self._color = color or theme.BRAND_CYAN
        self.setFixedSize(8, 8)
        self._opacity = 1.0
        self._anim = QPropertyAnimation(self, b"dot_opacity", self)
        self._anim.setDuration(2000)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.5)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)
        self._anim.start()

    @pyqtProperty(float)
    def dot_opacity(self):
        return self._opacity

    @dot_opacity.setter
    def dot_opacity(self, val):
        self._opacity = val
        self.update()

    def set_color(self, color):
        self._color = color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._opacity)
        p.setBrush(QBrush(QColor(self._color)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, 8, 8)
        p.end()


class InfoRow(QWidget):
    """Key-value row for device info."""
    def __init__(self, key, value, value_color=None):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        lbl_key = QLabel(key)
        lbl_key.setStyleSheet(
            f"color: {theme.BRAND_TEXT_SOFT}; font-family: {theme.FONT_MONO}; font-size: 11px;"
        )
        val_color = value_color or theme.BRAND_TEXT
        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(
            f"color: {val_color}; font-family: {theme.FONT_MONO}; "
            f"font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(lbl_key)
        layout.addStretch()
        layout.addWidget(lbl_val)


def make_toggle_row(label_text, default_state=False, parent_layout=None):
    """Helper to create a toggle + label row with proper spacing and bright text."""
    row = QHBoxLayout()
    row.setContentsMargins(0, 2, 0, 6)
    row.setSpacing(12)
    toggle = ToggleSwitch(default_state)
    lbl = QLabel(label_text)
    lbl.setStyleSheet(
        f"color: {theme.BRAND_TEXT_SOFT}; font-size: 12px; "
        f"font-family: {theme.FONT_MONO}; font-weight: 500;"
    )
    row.addWidget(toggle)
    row.addWidget(lbl)
    row.addStretch()
    if parent_layout is not None:
        parent_layout.addLayout(row)
    return toggle, row
