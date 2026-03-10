#!/usr/bin/env python3
# tab_image.py

import os
import cv2
import numpy as np
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout,
                             QPushButton, QScrollArea, QFrame, QGridLayout,
                             QComboBox, QFileDialog)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from ui_widgets import SliderWidget, ToggleSwitch, PresetChip, SectionHeader, Divider, make_toggle_row
from lut_engine import LUTS, generate_thumbnail
from bg_engine import VirtualBackgroundEngine
import theme

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PREVIEW_IMG = os.path.join(_SCRIPT_DIR, "lut_preview.jpg")

BG_MODES = [
    {"id": "none", "label": "Off", "icon": "🚫"},
    {"id": "blur", "label": "Blur Background", "icon": "🌫️"},
    {"id": "green", "label": "Green Screen", "icon": "🟩"},
    {"id": "image", "label": "Custom Image", "icon": "🖼️"},
]


class LUTCard(QPushButton):
    def __init__(self, lut_id, lut_name, lut_fn, ref_frame, parent=None):
        super().__init__(parent)
        self.lut_id = lut_id; self.lut_fn = lut_fn
        self.setCheckable(True); self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(100, 74)
        layout = QVBoxLayout(self); layout.setContentsMargins(4,4,4,4); layout.setSpacing(2)
        self.thumb_label = QLabel(); self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setFixedHeight(48); self.thumb_label.setStyleSheet("background:#0D1117; border-radius:4px;")
        layout.addWidget(self.thumb_label)
        self.name_label = QLabel(lut_name); self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet(f"color:{theme.BRAND_TEXT_SOFT}; font-size:9px; font-family:{theme.FONT_MONO}; font-weight:600;")
        layout.addWidget(self.name_label)
        if ref_frame is not None: self._set_thumbnail(ref_frame)
        self._apply_style(False)

    def _set_thumbnail(self, bgr_frame):
        try:
            thumb = generate_thumbnail(bgr_frame, self.lut_fn, 92, 48)
            rgb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            q = QImage(rgb.data, w, h, ch*w, QImage.Format.Format_RGB888)
            self.thumb_label.setPixmap(QPixmap.fromImage(q))
        except: pass

    def _apply_style(self, active):
        tc = theme.BRAND_CYAN if active else theme.BRAND_TEXT_SOFT
        self.name_label.setStyleSheet(f"color:{tc}; font-size:9px; font-family:{theme.FONT_MONO}; font-weight:600;")
        if active:
            self.setStyleSheet(f"QPushButton{{ background-color:rgba(0,212,170,24); border:1.5px solid {theme.BRAND_CYAN}; border-radius:8px; padding:0; }}")
        else:
            self.setStyleSheet(f"QPushButton{{ background-color:{theme.BRAND_CARD}; border:1px solid {theme.BRAND_BORDER}; border-radius:8px; padding:0; }} QPushButton:hover{{ border:1px solid rgba(0,212,170,96); }}")


class ImageTab(QWidget):
    lutChanged = pyqtSignal(object)
    mirrorChanged = pyqtSignal(bool)
    flipChanged = pyqtSignal(bool)
    bgChanged = pyqtSignal(str, str)     # mode, image_path
    bgBlurChanged = pyqtSignal(int)

    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self._active_lut_id = "natural"
        self._bg_image_path = ""

        self._ref_frame = None
        if os.path.exists(_PREVIEW_IMG):
            self._ref_frame = cv2.imread(_PREVIEW_IMG)

        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0)
        self.scroll_area = QScrollArea(); self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea{border:none;background:transparent;}QWidget#ScrollContent{background:transparent;}")
        self.content = QWidget(); self.content.setObjectName("ScrollContent")
        layout = QVBoxLayout(self.content); layout.setContentsMargins(16,16,16,16); layout.setSpacing(0)

        # ── IMAGE CONTROLS ──
        btn_reset = QPushButton("Reset All")
        btn_reset.setStyleSheet(f"border:1px solid {theme.BRAND_BORDER}; color:{theme.BRAND_TEXT_SOFT}; font-size:10px; padding:3px 10px; border-radius:5px; font-family:{theme.FONT_MONO};")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor); btn_reset.clicked.connect(self._on_reset_clicked)
        layout.addWidget(SectionHeader("🎨", "Image Controls", btn_reset))

        self.s_bright = SliderWidget("Brightness", 0, 100, 50)
        self.s_contrast = SliderWidget("Contrast", 0, 100, 50)
        self.s_sat = SliderWidget("Saturation", 0, 100, 50)
        self.s_sharp = SliderWidget("Sharpness", 0, 100, 50)
        self.s_hue = SliderWidget("Hue", -15, 15, 0)
        for s, c in [(self.s_bright,"brightness"),(self.s_contrast,"contrast"),
                     (self.s_sat,"saturation"),(self.s_sharp,"sharpness"),(self.s_hue,"hue")]:
            layout.addWidget(s); s.valueChanged.connect(lambda v, ctrl=c: self.backend.set_control(ctrl, v))

        layout.addWidget(Divider())

        # ── FOCUS ──
        layout.addWidget(SectionHeader("🔍", "Focus"))
        self.t_af, _ = make_toggle_row("Auto Focus", True, layout)
        self.s_focus = SliderWidget("Manual Focus", 0, 100, 50); self.s_focus.setDisabled(True)
        layout.addWidget(self.s_focus)
        self.t_af.toggled.connect(self._on_af_toggled)
        self.s_focus.valueChanged.connect(lambda v: self.backend.set_control("focus_absolute", v))

        layout.addWidget(Divider())

        # ── MIRROR & FLIP ──
        layout.addWidget(SectionHeader("🪞", "Mirror & Flip"))
        mn = QLabel("Software-based — applies to preview and virtual camera")
        mn.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM}; font-size:10px; font-family:{theme.FONT_MONO}; margin-bottom:8px;")
        layout.addWidget(mn)
        self.t_mirror, _ = make_toggle_row("Mirror (Horizontal)", False, layout)
        self.t_flip, _ = make_toggle_row("Flip (Vertical)", False, layout)
        self.t_mirror.toggled.connect(lambda v: self.mirrorChanged.emit(v))
        self.t_flip.toggled.connect(lambda v: self.flipChanged.emit(v))

        layout.addWidget(Divider())

        # ── VIRTUAL BACKGROUND ──
        layout.addWidget(SectionHeader("🎭", "Virtual Background"))

        if not VirtualBackgroundEngine.is_available():
            lbl_no_mp = QLabel("⚠  mediapipe not installed — virtual backgrounds disabled")
            lbl_no_mp.setWordWrap(True)
            lbl_no_mp.setStyleSheet(f"color:{theme.BRAND_WARN}; font-size:10px; font-family:{theme.FONT_MONO}; margin-bottom:6px;")
            layout.addWidget(lbl_no_mp)
            lbl_install = QLabel("Install:  pip install mediapipe --break-system-packages")
            lbl_install.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM}; font-size:10px; font-family:{theme.FONT_MONO}; margin-bottom:8px;")
            layout.addWidget(lbl_install)

        lbl_bg_mode = QLabel("MODE")
        lbl_bg_mode.setStyleSheet(f"color:{theme.BRAND_TEXT_SOFT}; font-size:10px; font-family:{theme.FONT_MONO}; letter-spacing:0.5px; font-weight:600; margin-bottom:6px;")
        layout.addWidget(lbl_bg_mode)

        self.bg_combo = QComboBox()
        self.bg_combo.setStyleSheet(f"""
            QComboBox{{ background-color:{theme.BRAND_DARK}; border:1px solid {theme.BRAND_BORDER};
                border-radius:6px; padding:6px 10px; color:{theme.BRAND_TEXT};
                font-family:{theme.FONT_MONO}; font-size:11px; min-width:0; }}
            QComboBox:focus{{ border:1px solid {theme.BRAND_CYAN}; }}
            QComboBox::drop-down{{ border:none; }}
            QComboBox QAbstractItemView{{ background-color:{theme.BRAND_CARD}; border:1px solid {theme.BRAND_BORDER};
                color:{theme.BRAND_TEXT}; selection-background-color:rgba(0,212,170,48);
                font-family:{theme.FONT_MONO}; font-size:11px; }}
        """)
        for m in BG_MODES:
            self.bg_combo.addItem(f"{m['icon']}  {m['label']}", m["id"])
        self.bg_combo.setCurrentIndex(0)
        if not VirtualBackgroundEngine.is_available():
            self.bg_combo.setDisabled(True)
        self.bg_combo.currentIndexChanged.connect(self._on_bg_mode_changed)
        layout.addWidget(self.bg_combo)
        layout.addSpacing(8)

        # Blur strength slider (hidden unless blur mode)
        self.s_blur = SliderWidget("Blur Strength", 5, 99, 21)
        self.s_blur.hide()
        self.s_blur.valueChanged.connect(self._on_blur_strength_changed)
        layout.addWidget(self.s_blur)

        # Image picker (hidden unless image mode)
        self.img_picker_row = QWidget()
        ipr = QHBoxLayout(self.img_picker_row); ipr.setContentsMargins(0,0,0,0); ipr.setSpacing(8)
        self.btn_pick_img = QPushButton("Choose Image...")
        self.btn_pick_img.setStyleSheet(
            f"border:1px solid {theme.BRAND_BORDER}; color:{theme.BRAND_TEXT_SOFT}; "
            f"font-size:10px; padding:5px 12px; border-radius:5px; font-family:{theme.FONT_MONO};")
        self.btn_pick_img.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pick_img.clicked.connect(self._pick_bg_image)
        ipr.addWidget(self.btn_pick_img)
        self.lbl_img_name = QLabel("No image selected")
        self.lbl_img_name.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM}; font-size:10px; font-family:{theme.FONT_MONO};")
        ipr.addWidget(self.lbl_img_name, stretch=1)
        self.img_picker_row.hide()
        layout.addWidget(self.img_picker_row)

        # Background preview thumbnail
        self.bg_preview = QLabel()
        self.bg_preview.setFixedHeight(80)
        self.bg_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bg_preview.setStyleSheet(f"background:#0D1117; border:1px solid {theme.BRAND_BORDER}; border-radius:6px;")
        self.bg_preview.hide()
        layout.addWidget(self.bg_preview)

        # Show acceleration status
        from bg_engine import _ACCEL
        accel_labels = {"cuda": "CUDA (NVIDIA GPU)", "opencl": "OpenCL (GPU)", "cpu": "CPU (half-res at 4K)"}
        accel_str = accel_labels.get(_ACCEL, "CPU")
        accel_color = theme.BRAND_GREEN if _ACCEL in ("cuda", "opencl") else theme.BRAND_TEXT_DIM
        bg_note = QLabel(f"Acceleration: {accel_str}")
        bg_note.setStyleSheet(f"color:{accel_color}; font-size:10px; font-family:{theme.FONT_MONO}; font-weight:600; margin-top:6px;")
        layout.addWidget(bg_note)

        if _ACCEL == "cpu":
            tip = QLabel("Install opencv-cuda (NVIDIA) for GPU acceleration\nAMD GPUs use OpenCL automatically if drivers support it")
            tip.setWordWrap(True)
            tip.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM}; font-size:9px; font-family:{theme.FONT_MONO}; margin-top:2px;")
            layout.addWidget(tip)

        layout.addWidget(Divider())

        # ── LUTs ──
        layout.addWidget(SectionHeader("🎬", "LUTs"))
        lh = QLabel("Applied to preview and virtual camera output")
        lh.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM}; font-size:10px; font-family:{theme.FONT_MONO}; margin-bottom:8px;")
        layout.addWidget(lh)
        self.lut_grid = QGridLayout(); self.lut_grid.setSpacing(6)
        self.lut_cards = []
        for i, lut in enumerate(LUTS):
            card = LUTCard(lut["id"], lut["name"], lut["fn"], self._ref_frame)
            if lut["id"] == "natural": card.setChecked(True); card._apply_style(True)
            card.clicked.connect(lambda checked, c=card: self._on_lut_selected(c))
            self.lut_cards.append(card); self.lut_grid.addWidget(card, i//3, i%3)
        layout.addLayout(self.lut_grid)

        layout.addWidget(Divider())

        # ── WHITE BALANCE ──
        layout.addWidget(SectionHeader("🌡️", "White Balance"))
        self.t_awb, _ = make_toggle_row("Auto White Balance", True, layout)
        self.s_wb_temp = SliderWidget("Temperature", 2000, 10000, 6400, "K", is_accent=True)
        self.s_wb_temp.setDisabled(True); layout.addWidget(self.s_wb_temp)
        self.t_awb.toggled.connect(self._on_awb_toggled)
        self.s_wb_temp.valueChanged.connect(lambda v: self.backend.set_control("white_balance_temperature", v))

        layout.addWidget(Divider())

        # ══ LOCKED ══
        lh2 = QLabel("🔒  FIRMWARE-LOCKED CONTROLS")
        lh2.setStyleSheet(f"color:{theme.BRAND_RED}; font-size:11px; font-weight:700; font-family:{theme.FONT_MONO}; letter-spacing:0.8px; margin-bottom:6px;")
        layout.addWidget(lh2)
        ln = QLabel("These controls exist in UVC but don't respond on Linux without Insta360's firmware.")
        ln.setWordWrap(True); ln.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM}; font-size:10px; font-family:{theme.FONT_MONO}; margin-bottom:12px;")
        layout.addWidget(ln)

        layout.addWidget(SectionHeader("📷", "Pan & Tilt"))
        self.s_pan = SliderWidget("Pan", -145, 145, 0); self.s_pan.setDisabled(True); layout.addWidget(self.s_pan)
        self.s_tilt = SliderWidget("Tilt", -90, 100, 0); self.s_tilt.setDisabled(True); layout.addWidget(self.s_tilt)
        layout.addSpacing(8)
        layout.addWidget(SectionHeader("☀️", "Exposure"))
        self.s_exp = SliderWidget("Exposure", 0, 1000, 166, is_warn=True); self.s_exp.setDisabled(True); layout.addWidget(self.s_exp)
        self.s_gain = SliderWidget("Gain", 0, 100, 30, is_warn=True); self.s_gain.setDisabled(True); layout.addWidget(self.s_gain)
        self.t_hdr, _ = make_toggle_row("HDR (Proprietary)", False, layout); self.t_hdr.setDisabled(True)

        layout.addStretch()
        self.scroll_area.setWidget(self.content); main_layout.addWidget(self.scroll_area)

    # ── Virtual Background ──
    def _on_bg_mode_changed(self, idx):
        if idx < 0 or idx >= len(BG_MODES): return
        mode = BG_MODES[idx]["id"]
        self.s_blur.setVisible(mode == "blur")
        self.img_picker_row.setVisible(mode == "image")
        self.bg_preview.setVisible(mode == "image" and bool(self._bg_image_path))
        self.bgChanged.emit(mode, self._bg_image_path if mode == "image" else "")

    def _on_blur_strength_changed(self, val):
        # Ensure odd
        if val % 2 == 0: val += 1
        self.bgBlurChanged.emit(val)

    def _pick_bg_image(self):
        # Use real user's home, not root's
        home = os.path.expanduser("~")
        if os.getuid() == 0:
            real_user = os.environ.get("SUDO_USER", "")
            if real_user:
                home = os.path.expanduser(f"~{real_user}")
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Background Image", home,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self._bg_image_path = path
            self.lbl_img_name.setText(os.path.basename(path))
            # Show thumbnail
            try:
                img = cv2.imread(path)
                if img is not None:
                    thumb = cv2.resize(img, (160, 80), interpolation=cv2.INTER_LINEAR)
                    rgb = cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    q = QImage(rgb.data, w, h, ch*w, QImage.Format.Format_RGB888)
                    self.bg_preview.setPixmap(QPixmap.fromImage(q))
                    self.bg_preview.show()
            except: pass
            self.bgChanged.emit("image", path)

    # ── LUTs ──
    def _on_lut_selected(self, card):
        for c in self.lut_cards: c.setChecked(c is card); c._apply_style(c is card)
        self._active_lut_id = card.lut_id
        self.lutChanged.emit(None if card.lut_id == "natural" else card.lut_fn)

    def _on_af_toggled(self, is_auto):
        self.s_focus.setDisabled(is_auto); self.backend.set_control("focus_automatic_continuous", 1 if is_auto else 0)
    def _on_awb_toggled(self, is_auto):
        self.s_wb_temp.setDisabled(is_auto); self.backend.set_control("white_balance_automatic", 1 if is_auto else 0)

    def _on_reset_clicked(self):
        self.backend.reset_to_defaults()
        for s, v in [(self.s_bright,50),(self.s_contrast,50),(self.s_sat,50),(self.s_sharp,50),(self.s_hue,0)]:
            s.set_value(v)
        self.t_af.set_checked(True); self.s_focus.setDisabled(True)
        self.t_awb.set_checked(True); self.s_wb_temp.setDisabled(True)
        self.t_mirror.set_checked(False); self.t_flip.set_checked(False)
        self.mirrorChanged.emit(False); self.flipChanged.emit(False)
        for c in self.lut_cards:
            is_nat = c.lut_id == "natural"; c.setChecked(is_nat); c._apply_style(is_nat)
        self._active_lut_id = "natural"; self.lutChanged.emit(None)
        self.bg_combo.setCurrentIndex(0); self._bg_image_path = ""
        self.bgChanged.emit("none", "")
