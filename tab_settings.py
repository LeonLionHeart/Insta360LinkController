#!/usr/bin/env python3
# tab_settings.py

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QFrame, QScrollArea, QPushButton, QDialog, QTextEdit)
from PyQt6.QtCore import Qt
from ui_widgets import SectionHeader, PresetChip, Divider, InfoRow
import theme


class V4L2Dialog(QDialog):
    def __init__(self, commands_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("v4l2-ctl Commands")
        self.setMinimumSize(550, 450)
        self.setStyleSheet(f"QDialog {{ background-color: {theme.BRAND_PANEL}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(f"background-color: {theme.BRAND_PANEL}; border-bottom: 1px solid {theme.BRAND_BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 16, 20, 16)
        hl.addWidget(QLabel("🐧  v4l2-ctl Commands"))
        hl.addStretch()
        bx = QPushButton("✕")
        bx.setStyleSheet(f"background:transparent; border:none; color:{theme.BRAND_TEXT_SOFT}; font-size:18px; padding:0;")
        bx.setCursor(Qt.CursorShape.PointingHandCursor)
        bx.clicked.connect(self.close)
        hl.addWidget(bx)
        layout.addWidget(header)

        body = QWidget()
        body.setStyleSheet(f"background-color: {theme.BRAND_PANEL};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 20, 20, 20)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setText(commands_text)
        self.text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {theme.BRAND_DARK}; border: 1px solid {theme.BRAND_BORDER};
                border-radius: 10px; padding: 16px; font-size: 11px;
                color: {theme.BRAND_CYAN}; font-family: {theme.FONT_MONO};
            }}
        """)
        bl.addWidget(self.text_edit)
        layout.addWidget(body, stretch=1)

        footer = QWidget()
        footer.setStyleSheet(f"background-color: {theme.BRAND_PANEL}; border-top: 1px solid {theme.BRAND_BORDER};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 12, 20, 12)
        fl.addStretch()

        bc = QPushButton("Copy to Clipboard")
        bc.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.BRAND_CYAN}; border: none; color: #000;
                font-size: 12px; font-weight: 700; font-family: {theme.FONT_MONO};
                padding: 8px 20px; border-radius: 8px;
            }}
            QPushButton:hover {{ background-color: {theme.BRAND_CYAN_DIM}; }}
        """)
        bc.setCursor(Qt.CursorShape.PointingHandCursor)
        bc.clicked.connect(lambda: self._copy(commands_text))
        fl.addWidget(bc)

        bcl = QPushButton("Close")
        bcl.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {theme.BRAND_BORDER};
                color: {theme.BRAND_TEXT_SOFT}; font-size: 12px;
                font-family: {theme.FONT_MONO}; padding: 8px 20px; border-radius: 8px;
            }}
            QPushButton:hover {{ border-color: rgba(0,212,170,96); color: {theme.BRAND_TEXT}; }}
        """)
        bcl.setCursor(Qt.CursorShape.PointingHandCursor)
        bcl.clicked.connect(self.close)
        fl.addWidget(bcl)
        layout.addWidget(footer)

    def _copy(self, text):
        from PyQt6.QtWidgets import QApplication
        cb = QApplication.clipboard()
        if cb:
            cb.setText(text)


class SettingsTab(QWidget):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QWidget#SettingsScrollContent { background: transparent; }
        """)

        content = QWidget()
        content.setObjectName("SettingsScrollContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        # ── CAMERA SETTINGS ──
        layout.addWidget(SectionHeader("📷", "Camera"))

        lbl_flicker = QLabel("ANTI-FLICKER")
        lbl_flicker.setStyleSheet(
            f"color: {theme.BRAND_TEXT_SOFT}; font-size: 11px; font-family: {theme.FONT_MONO}; "
            f"letter-spacing: 0.5px; margin-bottom: 6px;"
        )
        layout.addWidget(lbl_flicker)

        fl = QHBoxLayout()
        fl.setSpacing(6)
        self.btn_off = PresetChip("Off")
        self.btn_50hz = PresetChip("50 Hz")
        self.btn_60hz = PresetChip("60 Hz")
        self.btn_60hz.setChecked(True)
        fl.addWidget(self.btn_off)
        fl.addWidget(self.btn_50hz)
        fl.addWidget(self.btn_60hz)
        fl.addStretch()
        layout.addLayout(fl)

        self.btn_off.clicked.connect(lambda: self._set_flicker(0, self.btn_off))
        self.btn_50hz.clicked.connect(lambda: self._set_flicker(1, self.btn_50hz))
        self.btn_60hz.clicked.connect(lambda: self._set_flicker(2, self.btn_60hz))

        layout.addWidget(Divider())

        # ── DEVICE INFO ──
        layout.addWidget(SectionHeader("ℹ️", "Device Info"))

        info_card = QFrame()
        info_card.setStyleSheet(
            f"background-color: {theme.BRAND_DARK}; border: 1px solid {theme.BRAND_BORDER}; border-radius: 10px;"
        )
        il = QVBoxLayout(info_card)
        il.setSpacing(0)
        il.setContentsMargins(14, 10, 14, 10)

        for key, val, color in [
            ("Model", "Insta360 Link 2C Pro", None),
            ("Vendor ID", "0x2e1a", None),
            ("Product ID", "0x4c01", None),
            ("Protocol", "UVC 1.10 / UAC", None),
            ("Sensor", '1/1.3" · Dual ISO', None),
            ("Driver", "uvcvideo (v4l2)", theme.BRAND_CYAN),
            ("Device", self.backend.device, None),
        ]:
            r = InfoRow(key, val, color)
            r.setFixedHeight(28)
            il.addWidget(r)
        layout.addWidget(info_card)

        layout.addWidget(Divider())

        # ── V4L2 CONTROLS ──
        layout.addWidget(SectionHeader("🐧", "v4l2 Controls"))

        self.btn_generate = QPushButton("Generate v4l2-ctl Commands")
        self.btn_generate.setObjectName("GradientBtn")
        self.btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_generate.clicked.connect(self._show_v4l2_dialog)
        layout.addWidget(self.btn_generate)

        layout.addSpacing(8)
        ld = QLabel(
            "Export current settings as v4l2-ctl shell commands you can "
            "run on your system or add to a startup script."
        )
        ld.setWordWrap(True)
        ld.setStyleSheet(f"color: {theme.BRAND_TEXT_SOFT}; font-size: 10px; font-family: {theme.FONT_MONO};")
        layout.addWidget(ld)

        layout.addWidget(Divider())

        # ── ABOUT ──
        layout.addWidget(SectionHeader("💡", "About"))

        for text in [
            "Open-source Linux controller for Insta360 Link series webcams. "
            "Uses the V4L2 (Video4Linux2) API to communicate with UVC-compliant devices.",
            "Note: Some AI features (virtual background, beautify, smart whiteboard "
            "enhancement) require the proprietary Insta360 Virtual Camera and are not "
            "available on Linux. Basic controls, zoom, image settings, and resolution/FPS "
            "work fully via V4L2.",
        ]:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"color: {theme.BRAND_TEXT_SOFT}; font-size: 10px; "
                f"font-family: {theme.FONT_MONO}; margin-bottom: 8px;"
            )
            layout.addWidget(lbl)

        layout.addStretch()
        self.scroll_area.setWidget(content)
        main_layout.addWidget(self.scroll_area)

    def _set_flicker(self, val, active_btn):
        for b in [self.btn_off, self.btn_50hz, self.btn_60hz]:
            b.setChecked(b is active_btn)
        self.backend.set_control("power_line_frequency", val)

    def _show_v4l2_dialog(self):
        mw = self.window()
        w = getattr(mw, 'current_w', 1920)
        h = getattr(mw, 'current_h', 1080)
        fps = getattr(mw, 'current_fps', 30)
        dev = self.backend.device
        cmds = ["# Insta360 Link — v4l2-ctl Commands", "# Generated by Link Controller for Linux", ""]
        cmds.append("# Image Controls")
        for ctrl, default in [("brightness", 50), ("contrast", 50), ("saturation", 50), ("sharpness", 50), ("hue", 0)]:
            val = self.backend.get_control(ctrl)
            cmds.append(f"v4l2-ctl -d {dev} -c {ctrl}={val if val is not None else default}")
        cmds += ["", "# White Balance"]
        awb = self.backend.get_control("white_balance_automatic")
        cmds.append(f"v4l2-ctl -d {dev} -c white_balance_automatic={awb if awb is not None else 1}")
        if awb == 0:
            temp = self.backend.get_control("white_balance_temperature")
            if temp is not None:
                cmds.append(f"v4l2-ctl -d {dev} -c white_balance_temperature={temp}")
        cmds += ["", "# Focus"]
        afc = self.backend.get_control("focus_automatic_continuous")
        cmds.append(f"v4l2-ctl -d {dev} -c focus_automatic_continuous={afc if afc is not None else 1}")
        if afc == 0:
            foc = self.backend.get_control("focus_absolute")
            if foc is not None:
                cmds.append(f"v4l2-ctl -d {dev} -c focus_absolute={foc}")
        cmds += ["", "# Zoom"]
        zoom = self.backend.get_control("zoom_absolute")
        cmds.append(f"v4l2-ctl -d {dev} -c zoom_absolute={zoom if zoom is not None else 100}")
        cmds += ["", "# Power Line Frequency"]
        plf = self.backend.get_control("power_line_frequency")
        cmds.append(f"v4l2-ctl -d {dev} -c power_line_frequency={plf if plf is not None else 2}")
        cmds += ["", "# Resolution & Frame Rate"]
        cmds.append(f"v4l2-ctl -d {dev} --set-fmt-video=width={w},height={h},pixelformat=MJPG")
        cmds.append(f"v4l2-ctl -d {dev} --set-parm={fps}")
        V4L2Dialog("\n".join(cmds), self).exec()
