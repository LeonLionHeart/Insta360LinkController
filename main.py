#!/usr/bin/env python3
# main.py

import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                             QVBoxLayout, QLabel, QFrame, QTabWidget, QPushButton,
                             QComboBox, QInputDialog)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QLinearGradient, QColor, QPainter, QBrush, QFont
import theme
from backend_v4l2 import V4L2Backend
from preview_widget import CameraPreview
from tab_image import ImageTab
from tab_audio import AudioTab
from tab_files import FilesTab
from tab_settings import SettingsTab
from virtual_camera import VirtualCamera
from presets import PresetManager, DEFAULT_STATE
from ui_widgets import SliderWidget, SectionHeader, StatusDot, PresetChip

RESOLUTIONS = [
    {"label": "4K", "w": 3840, "h": 2160, "fps": [30, 25, 24]},
    {"label": "1080p", "w": 1920, "h": 1080, "fps": [60, 50, 30, 25, 24]},
    {"label": "720p", "w": 1280, "h": 720, "fps": [60, 50, 30, 25, 24]},
    {"label": "360p", "w": 640, "h": 360, "fps": [30, 25, 24]},
]
STOP_BTN = f"QPushButton{{background-color:rgba(255,71,87,25);border:1px solid rgba(255,71,87,100);color:{theme.BRAND_RED};border-radius:8px;padding:10px 0;font-weight:600;font-family:{theme.FONT_MONO};font-size:12px;}}QPushButton:hover{{background-color:rgba(255,71,87,50);border:1px solid {theme.BRAND_RED};}}"
START_BTN = f"QPushButton{{background-color:rgba(0,212,170,25);border:1px solid rgba(0,212,170,100);color:{theme.BRAND_CYAN};border-radius:8px;padding:10px 0;font-weight:600;font-family:{theme.FONT_MONO};font-size:12px;}}QPushButton:hover{{background-color:rgba(0,212,170,50);border:1px solid {theme.BRAND_CYAN};}}"

class BrandLogo(QWidget):
    def __init__(self, p=None): super().__init__(p); self.setFixedSize(32,32)
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0,0,32,32); g.setColorAt(0,QColor(theme.BRAND_CYAN)); g.setColorAt(1,QColor(theme.BRAND_CYAN_DIM))
        p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen); p.drawRoundedRect(0,0,32,32,8,8)
        p.setPen(QColor("#000")); p.setFont(QFont("JetBrains Mono",16,QFont.Weight.Black))
        p.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,"i"); p.end()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Insta360 Link Controller (Linux)")
        self.resize(1100, 850); self.setStyleSheet(theme.STYLESHEET)
        self.backend = V4L2Backend()
        cameras = self.backend.get_insta360_cameras()
        cam_name = "No Device"
        if cameras: cam_name, path = list(cameras.items())[0]; self.backend.set_device(path, cam_name)
        self.is_connected = self.backend.check_connection()
        self.preset_mgr = PresetManager(); self.vcam = VirtualCamera()
        active = self.preset_mgr.get_active()
        st = active.state if active else DEFAULT_STATE
        self.res_index = st.get("res_index",1); self.current_fps = st.get("fps",30)
        self.current_w = RESOLUTIONS[self.res_index]["w"]; self.current_h = RESOLUTIONS[self.res_index]["h"]

        central = QWidget(); self.setCentralWidget(central)
        ml = QVBoxLayout(central); ml.setContentsMargins(0,0,0,0); ml.setSpacing(0)

        # Top bar
        top = QFrame(); top.setFixedHeight(56)
        top.setStyleSheet(f"background-color:{theme.BRAND_PANEL};border-bottom:1px solid {theme.BRAND_BORDER};")
        tl = QHBoxLayout(top); tl.setContentsMargins(20,0,20,0); tl.setSpacing(14)
        tl.addWidget(BrandLogo())
        tb = QVBoxLayout(); tb.setSpacing(0); tb.addWidget(QLabel("Insta360 Link Controller")); tb.addWidget(QLabel("for Linux · v4l2 backend"))
        tl.addLayout(tb); tl.addStretch()
        self.status_dot = StatusDot(theme.BRAND_CYAN if self.is_connected else theme.BRAND_RED); tl.addWidget(self.status_dot)
        tl.addWidget(QLabel(cam_name if self.is_connected else "No Device")); tl.addSpacing(12)
        be = QPushButton("⌨ Export v4l2 Commands")
        be.setStyleSheet(f"background:transparent;border:1px solid {theme.BRAND_BORDER};border-radius:6px;color:{theme.BRAND_TEXT_SOFT};font-size:11px;padding:5px 12px;font-family:{theme.FONT_MONO};")
        be.setCursor(Qt.CursorShape.PointingHandCursor); be.clicked.connect(self._on_export); tl.addWidget(be); ml.addWidget(top)

        body = QHBoxLayout(); body.setContentsMargins(16,16,16,16); body.setSpacing(12); ml.addLayout(body)

        # Left
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(12)
        self.preview = CameraPreview(self.backend.device)
        self.preview.setMinimumSize(640,360); self.preview.set_virtual_camera(self.vcam)
        ll.addWidget(self.preview, stretch=1)

        # Res/FPS
        rc = QFrame(); rc.setObjectName("Card"); rl = QHBoxLayout(rc); rl.setContentsMargins(16,10,16,10); rl.setSpacing(6)
        rl.addWidget(QLabel("RESOLUTION")); rl.addSpacing(4)
        self.res_chips = []
        for i, r in enumerate(RESOLUTIONS):
            c = PresetChip(r["label"])
            if i == self.res_index: c.setChecked(True)
            c.clicked.connect(lambda _,idx=i: self._on_res(idx)); self.res_chips.append(c); rl.addWidget(c)
        sep = QFrame(); sep.setFixedSize(1,20); sep.setStyleSheet(f"background-color:{theme.BRAND_BORDER};")
        rl.addSpacing(8); rl.addWidget(sep); rl.addSpacing(8); rl.addWidget(QLabel("FPS")); rl.addSpacing(4)
        self.fps_box = QHBoxLayout(); self.fps_box.setSpacing(6); self.fps_chips = []; self._build_fps()
        rl.addLayout(self.fps_box); rl.addStretch(); ll.addWidget(rc)

        # Zoom
        zc = QFrame(); zc.setObjectName("Card"); zcl = QVBoxLayout(zc); zcl.setContentsMargins(16,12,16,12); zcl.setSpacing(8)
        brz = QPushButton("Reset"); brz.setStyleSheet(f"border:none;color:{theme.BRAND_TEXT_SOFT};font-size:10px;font-family:{theme.FONT_MONO};padding:0;")
        brz.setCursor(Qt.CursorShape.PointingHandCursor); zcl.addWidget(SectionHeader("🔍","Zoom",brz))
        zr = QHBoxLayout(); zr.setSpacing(10)
        def _zb(t):
            b = QPushButton(t); b.setFixedSize(30,30)
            b.setStyleSheet(f"QPushButton{{background-color:{theme.BRAND_CARD};border:1px solid {theme.BRAND_BORDER};border-radius:15px;color:{theme.BRAND_TEXT};font-size:16px;font-weight:700;padding:0;}}QPushButton:hover{{border-color:rgba(0,212,170,96);color:{theme.BRAND_CYAN};}}")
            b.setCursor(Qt.CursorShape.PointingHandCursor); return b
        bm = _zb("−"); zr.addWidget(bm)
        actual_zoom = st.get("zoom",100)
        if self.is_connected:
            hw = self.backend.get_control("zoom_absolute")
            if hw is not None: actual_zoom = hw
        self.s_zoom = SliderWidget("",100,400,actual_zoom); zr.addWidget(self.s_zoom, stretch=1)
        bp = _zb("+"); zr.addWidget(bp)
        self.lzv = QLabel(f"{actual_zoom/100:.1f}×")
        self.lzv.setStyleSheet(f"color:{theme.BRAND_CYAN};font-family:{theme.FONT_MONO};font-size:12px;font-weight:700;min-width:40px;")
        self.lzv.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter); zr.addWidget(self.lzv); zcl.addLayout(zr)
        self.s_zoom.valueChanged.connect(self._on_zoom)
        bm.clicked.connect(lambda: self.s_zoom.set_value(max(100,self.s_zoom.slider.value()-10)))
        bp.clicked.connect(lambda: self.s_zoom.set_value(min(400,self.s_zoom.slider.value()+10)))
        brz.clicked.connect(lambda: self.s_zoom.set_value(100)); ll.addWidget(zc)

        # Presets
        pc = QFrame(); pc.setObjectName("Card"); pcl = QVBoxLayout(pc); pcl.setContentsMargins(16,12,16,12); pcl.setSpacing(8)
        bsv = QPushButton("+ Save Current"); bsv.setObjectName("OutlineBtn"); bsv.setCursor(Qt.CursorShape.PointingHandCursor)
        bsv.clicked.connect(self._save_preset); pcl.addWidget(SectionHeader("🎬","Scene Presets",bsv))
        self.preset_row = QHBoxLayout(); self.preset_row.setSpacing(6); self.preset_chips = []; self._build_presets()
        pcl.addLayout(self.preset_row); ll.addWidget(pc)

        # Virtual Camera
        vc = QFrame(); vc.setObjectName("Card"); vcl = QVBoxLayout(vc); vcl.setContentsMargins(16,12,16,12); vcl.setSpacing(8)
        vcl.addWidget(SectionHeader("📹","Virtual Camera"))
        pr = QHBoxLayout(); pr.setSpacing(8); pr.addWidget(QLabel("PROFILE"))
        self.vcam_combo = QComboBox()
        self.vcam_combo.setStyleSheet(f"QComboBox{{background-color:{theme.BRAND_DARK};border:1px solid {theme.BRAND_BORDER};border-radius:6px;padding:5px 10px;color:{theme.BRAND_TEXT};font-family:{theme.FONT_MONO};font-size:11px;min-width:0;}}QComboBox:focus{{border:1px solid {theme.BRAND_CYAN};}}QComboBox::drop-down{{border:none;}}QComboBox QAbstractItemView{{background-color:{theme.BRAND_CARD};border:1px solid {theme.BRAND_BORDER};color:{theme.BRAND_TEXT};selection-background-color:rgba(0,212,170,48);font-family:{theme.FONT_MONO};font-size:11px;}}")
        self._fill_profiles(); pr.addWidget(self.vcam_combo, stretch=1)
        def _sb(t,rgb,tip):
            b = QPushButton(t); b.setFixedSize(28,28); b.setToolTip(tip); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"QPushButton{{background:rgba({rgb},20);border:1px solid rgba({rgb},65);border-radius:6px;color:rgba({rgb},255);font-size:16px;font-weight:700;padding:0;}}QPushButton:hover{{background:rgba({rgb},45);}}"); return b
        ba = _sb("+","0,212,170","Add"); ba.clicked.connect(self._add_profile); pr.addWidget(ba)
        brd = _sb("−","255,71,87","Remove"); brd.clicked.connect(self._rm_profile); pr.addWidget(brd); vcl.addLayout(pr)
        dr = QHBoxLayout(); dr.setContentsMargins(0,0,0,0); dr.setSpacing(8)
        bsd = QPushButton("⭐ Set as Default"); bsd.setStyleSheet(f"border:1px solid {theme.BRAND_BORDER};color:{theme.BRAND_TEXT_SOFT};font-size:10px;padding:3px 10px;border-radius:5px;font-family:{theme.FONT_MONO};")
        bsd.setCursor(Qt.CursorShape.PointingHandCursor); bsd.clicked.connect(self._set_default); dr.addWidget(bsd)
        self.lbl_def = QLabel(""); self.lbl_def.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM};font-size:10px;font-family:{theme.FONT_MONO};")
        dr.addWidget(self.lbl_def); dr.addStretch(); vcl.addLayout(dr); self._upd_def()
        self.btn_vcam = QPushButton("▶  Start Virtual Camera"); self.btn_vcam.setStyleSheet(START_BTN)
        self.btn_vcam.setCursor(Qt.CursorShape.PointingHandCursor); self.btn_vcam.clicked.connect(self._vcam_toggle); vcl.addWidget(self.btn_vcam)
        vsr = QHBoxLayout(); vsr.setContentsMargins(0,0,0,0); vsr.setSpacing(8)
        self.vdot = QLabel("●"); self.vdot.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM};font-size:12px;"); vsr.addWidget(self.vdot)
        self.vlbl = QLabel("Stopped"); self.vlbl.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM};font-size:10px;font-family:{theme.FONT_MONO};"); vsr.addWidget(self.vlbl); vsr.addStretch()
        self.vdev = QLabel(""); self.vdev.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM};font-size:10px;font-family:{theme.FONT_MONO};"); vsr.addWidget(self.vdev); vcl.addLayout(vsr)
        self.vinfo = QLabel(""); self.vinfo.setWordWrap(True); self.vinfo.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM};font-size:10px;font-family:{theme.FONT_MONO};"); vcl.addWidget(self.vinfo)
        if not VirtualCamera.is_module_installed():
            self.vinfo.setText("⚠  v4l2loopback not found"); self.vinfo.setStyleSheet(f"color:{theme.BRAND_WARN};font-size:10px;font-family:{theme.FONT_MONO};"); self.btn_vcam.setDisabled(True)
        else: self.vinfo.setText("Creates a virtual camera visible to OBS, Zoom, Discord, etc.")
        ll.addWidget(vc); body.addWidget(left, stretch=2)

        # Right
        right = QFrame(); right.setObjectName("Panel"); right.setFixedWidth(340)
        rrl = QVBoxLayout(right); rrl.setContentsMargins(0,0,0,0)
        self.tabs = QTabWidget()
        self.tab_image = ImageTab(self.backend); self.tab_audio = AudioTab(self.backend)
        self.tab_files = FilesTab(); self.tab_settings = SettingsTab(self.backend)
        self.tabs.addTab(self.tab_image, "🎨 Image"); self.tabs.addTab(self.tab_audio, "🔊 Audio")
        self.tabs.addTab(self.tab_files, "📁 Files"); self.tabs.addTab(self.tab_settings, "⚙️ Settings")
        rrl.addWidget(self.tabs); body.addWidget(right)

        # Wire
        self.preview.set_file_settings(self.tab_files.settings)
        self.preview.set_audio_settings(self.tab_audio.audio_settings, self.tab_audio.audio)
        self.preview.micToggled.connect(self._on_mic)
        self.tab_image.lutChanged.connect(self.preview.set_lut)
        self.tab_image.mirrorChanged.connect(self.preview.set_mirror)
        self.tab_image.flipChanged.connect(self.preview.set_flip)
        self.tab_image.bgChanged.connect(self.preview.set_virtual_background)
        self.tab_image.bgBlurChanged.connect(self.preview.set_bg_blur_strength)
        self.tab_audio.sourceChanged.connect(self._on_audio_source_changed)

        self._ht = QTimer(); self._ht.timeout.connect(self._chk)
        self._apply_state(st)
        if self.is_connected: self._apply_fmt()
        if VirtualCamera.is_module_installed() and self.is_connected:
            QTimer.singleShot(1500, self._auto_vcam)

    def _on_audio_source_changed(self):
        self.preview.set_audio_settings(self.tab_audio.audio_settings, self.tab_audio.audio)

    def _capture_state(self):
        return {"res_index":self.res_index,"fps":self.current_fps,"zoom":self.s_zoom.slider.value(),
            "brightness":self.tab_image.s_bright.slider.value(),"contrast":self.tab_image.s_contrast.slider.value(),
            "saturation":self.tab_image.s_sat.slider.value(),"sharpness":self.tab_image.s_sharp.slider.value(),
            "hue":self.tab_image.s_hue.slider.value(),"lut_id":self.tab_image._active_lut_id,
            "mirror_h":self.tab_image.t_mirror._checked,"flip_v":self.tab_image.t_flip._checked,
            "auto_focus":self.tab_image.t_af._checked,"focus":self.tab_image.s_focus.slider.value(),
            "auto_wb":self.tab_image.t_awb._checked,"wb_temp":self.tab_image.s_wb_temp.slider.value(),
            "bg_mode_idx":self.tab_image.bg_combo.currentIndex(),"bg_image_path":self.tab_image._bg_image_path,
            "bg_blur":self.tab_image.s_blur.slider.value()}

    def _apply_state(self, st):
        self.tab_image.s_bright.set_value(st.get("brightness",50)); self.tab_image.s_contrast.set_value(st.get("contrast",50))
        self.tab_image.s_sat.set_value(st.get("saturation",50)); self.tab_image.s_sharp.set_value(st.get("sharpness",50))
        self.tab_image.s_hue.set_value(st.get("hue",0))
        af = st.get("auto_focus",True); self.tab_image.t_af.set_checked(af); self.tab_image.s_focus.setDisabled(af)
        if not af: self.tab_image.s_focus.set_value(st.get("focus",50))
        awb = st.get("auto_wb",True); self.tab_image.t_awb.set_checked(awb); self.tab_image.s_wb_temp.setDisabled(awb)
        if not awb: self.tab_image.s_wb_temp.set_value(st.get("wb_temp",6400))
        m = st.get("mirror_h",False); f = st.get("flip_v",False)
        self.tab_image.t_mirror.set_checked(m); self.tab_image.t_flip.set_checked(f)
        self.preview.set_mirror(m); self.preview.set_flip(f)
        # Virtual background
        bgi = st.get("bg_mode_idx",0); self.tab_image._bg_image_path = st.get("bg_image_path","")
        self.tab_image.bg_combo.blockSignals(True); self.tab_image.bg_combo.setCurrentIndex(bgi); self.tab_image.bg_combo.blockSignals(False)
        modes = ["none","blur","green","image"]
        sm = modes[bgi] if bgi < len(modes) else "none"
        self.tab_image.s_blur.setVisible(sm == "blur")
        self.tab_image.img_picker_row.setVisible(sm == "image")
        blur_v = st.get("bg_blur",21); self.tab_image.s_blur.set_value(blur_v)
        self.preview.set_virtual_background(sm, self.tab_image._bg_image_path)
        self.preview.set_bg_blur_strength(blur_v)
        # LUT
        lid = st.get("lut_id","natural")
        for card in self.tab_image.lut_cards:
            is_it = card.lut_id == lid; card.setChecked(is_it); card._apply_style(is_it)
            if is_it: self.tab_image._active_lut_id = lid; self.preview.set_lut(None if lid=="natural" else card.lut_fn)

    def _on_mic(self, muted):
        self.tab_audio.t_mute.set_checked(muted); self.tab_audio._on_mute_toggled(muted)

    # Presets
    def _build_presets(self):
        for c in self.preset_chips: self.preset_row.removeWidget(c); c.deleteLater()
        self.preset_chips = []; an = self.preset_mgr.last_active
        for n in self.preset_mgr.get_names():
            c = PresetChip(n)
            if n == an: c.setChecked(True)
            c.clicked.connect(lambda _,nm=n: self._load_preset(nm)); self.preset_chips.append(c); self.preset_row.addWidget(c)
        self.preset_row.addStretch()
    def _load_preset(self, name):
        p = self.preset_mgr.get_preset(name)
        if not p: return
        self.preset_mgr.set_active(name)
        for c in self.preset_chips: c.setChecked(c.text()==name)
        s = p.state; ri = s.get("res_index",1)
        if ri != self.res_index: self._on_res(ri)
        fp = s.get("fps",30)
        if fp != self.current_fps: self._on_fps(fp)
        self.s_zoom.set_value(s.get("zoom",100)); self._apply_state(s)
    def _save_preset(self):
        an = self.preset_mgr.last_active
        for c in self.preset_chips:
            if c.isChecked(): an = c.text(); break
        self.preset_mgr.save_preset(an, self._capture_state()); self._build_presets()
        self.preview._show_toast(f"Saved: {an}")

    # VCam
    def _fill_profiles(self):
        self.vcam_combo.blockSignals(True); self.vcam_combo.clear()
        pm = self.vcam.profile_manager; d = pm.get_default(); si = 0
        for i,n in enumerate(pm.get_names()):
            sfx = " ⭐" if d and d.name==n else ""; self.vcam_combo.addItem(f"{n}{sfx}",n)
            if d and d.name==n: si = i
        self.vcam_combo.setCurrentIndex(si); self.vcam_combo.blockSignals(False)
    def _upd_def(self):
        d = self.vcam.profile_manager.get_default(); self.lbl_def.setText(f"Default: {d.name}" if d else "")
    def _add_profile(self):
        n,ok = QInputDialog.getText(self,"New Profile","Profile name:")
        if ok and n.strip(): self.vcam.profile_manager.add_profile(n.strip()); self._fill_profiles(); idx = self.vcam_combo.findData(n.strip()); self.vcam_combo.setCurrentIndex(idx) if idx>=0 else None
    def _rm_profile(self):
        idx = self.vcam_combo.currentIndex()
        if idx<0: return
        pm = self.vcam.profile_manager
        if len(pm.profiles)<=1: return
        pm.remove_profile(self.vcam_combo.itemData(idx)); self._fill_profiles(); self._upd_def()
    def _set_default(self):
        idx = self.vcam_combo.currentIndex()
        if idx<0: return
        self.vcam.profile_manager.set_default(self.vcam_combo.itemData(idx)); self._fill_profiles(); self._upd_def()
    def _auto_vcam(self):
        if self.vcam.is_active: return
        d = self.vcam.profile_manager.get_default()
        if d: idx = self.vcam_combo.findData(d.name); self.vcam_combo.setCurrentIndex(idx) if idx>=0 else None
        self._vcam_start()
    def _vcam_toggle(self):
        if self.vcam.is_active: self._vcam_stop()
        else: self._vcam_start()
    def _vcam_start(self):
        idx = self.vcam_combo.currentIndex(); name = self.vcam_combo.itemData(idx) if idx>=0 else "Default"
        if self.vcam.start(name or "Default", self.current_w, self.current_h, self.current_fps):
            self.btn_vcam.setText("⏹  Stop Virtual Camera"); self.btn_vcam.setStyleSheet(STOP_BTN)
            self.vdot.setStyleSheet(f"color:{theme.BRAND_GREEN};font-size:12px;")
            self.vlbl.setText("Live"); self.vlbl.setStyleSheet(f"color:{theme.BRAND_GREEN};font-size:10px;font-family:{theme.FONT_MONO};font-weight:600;")
            self.vdev.setText(self.vcam.device_path); self.vdev.setStyleSheet(f"color:{theme.BRAND_CYAN};font-size:10px;font-family:{theme.FONT_MONO};")
            self.vinfo.setText(f"Visible as: {self.vcam.card_label}\nDevice: {self.vcam.device_path}  ·  {self.current_w}×{self.current_h} @ {self.current_fps}fps")
            self.vinfo.setStyleSheet(f"color:{theme.BRAND_TEXT_SOFT};font-size:10px;font-family:{theme.FONT_MONO};")
            self.vcam_combo.setDisabled(True); self._ht.start(2000)
        else:
            self.vinfo.setText(f"⚠  {self.vcam.get_error() or 'Error'}"); self.vinfo.setStyleSheet(f"color:{theme.BRAND_RED};font-size:10px;font-family:{theme.FONT_MONO};")
    def _vcam_stop(self):
        self.vcam.stop(); self._ht.stop()
        self.btn_vcam.setText("▶  Start Virtual Camera"); self.btn_vcam.setStyleSheet(START_BTN)
        self.vdot.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM};font-size:12px;")
        self.vlbl.setText("Stopped"); self.vlbl.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM};font-size:10px;font-family:{theme.FONT_MONO};")
        self.vdev.setText(""); self.vinfo.setText("Creates a virtual camera visible to OBS, Zoom, Discord, etc.")
        self.vinfo.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM};font-size:10px;font-family:{theme.FONT_MONO};"); self.vcam_combo.setDisabled(False)
    def _chk(self):
        if self.vcam.is_active: return
        self._vcam_stop(); err = self.vcam.get_error()
        if err: self.vinfo.setText(f"⚠  {err}"); self.vinfo.setStyleSheet(f"color:{theme.BRAND_RED};font-size:10px;font-family:{theme.FONT_MONO};")

    # Res/FPS
    def _build_fps(self):
        for c in self.fps_chips: self.fps_box.removeWidget(c); c.deleteLater()
        self.fps_chips.clear(); avail = RESOLUTIONS[self.res_index]["fps"]
        for f in avail:
            c = PresetChip(str(f))
            if f==self.current_fps or (self.current_fps not in avail and f==avail[0]):
                c.setChecked(True)
                if self.current_fps not in avail: self.current_fps = avail[0]
            c.clicked.connect(lambda _,fv=f: self._on_fps(fv)); self.fps_chips.append(c); self.fps_box.addWidget(c)
    def _on_res(self, idx):
        self.res_index = idx; self.current_w = RESOLUTIONS[idx]["w"]; self.current_h = RESOLUTIONS[idx]["h"]
        for i,c in enumerate(self.res_chips): c.setChecked(i==idx)
        self._build_fps(); self._apply_fmt()
        if self.vcam.is_active:
            self.vinfo.setText("⚠  Resolution changed — restart virtual camera"); self.vinfo.setStyleSheet(f"color:{theme.BRAND_WARN};font-size:10px;font-family:{theme.FONT_MONO};")
    def _on_fps(self, fv):
        self.current_fps = fv
        for c in self.fps_chips: c.setChecked(c.text()==str(fv))
        self._apply_fmt()
    def _apply_fmt(self):
        if self.is_connected:
            self.backend.set_format(self.current_w, self.current_h, self.current_fps)
            self.preview.start(self.backend.device, self.current_w, self.current_h, self.current_fps)
        self.preview.set_resolution_text(self.current_w, self.current_h, self.current_fps)
    def _on_zoom(self, v):
        self.lzv.setText(f"{v/100:.1f}×"); self.backend.set_control("zoom_absolute",v); self.preview.set_zoom_display(v)
    def _on_export(self):
        self.tabs.setCurrentWidget(self.tab_settings); self.tab_settings._show_v4l2_dialog()
    def closeEvent(self, event):
        self.preset_mgr.save_preset(self.preset_mgr.last_active, self._capture_state())
        self.preview.shutdown(); self.tab_audio.stop_stream()
        if self.vcam.is_active: self.vcam.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv); window = MainWindow(); window.show(); sys.exit(app.exec())
