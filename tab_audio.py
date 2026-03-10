#!/usr/bin/env python3
# tab_audio.py

import subprocess
import os
import re
import math
import json
import shutil
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QScrollArea, QFrame, QComboBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush, QLinearGradient, QPen
from ui_widgets import SectionHeader, SliderWidget, Divider, make_toggle_row
import theme

try:
    import numpy as np
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

INSTA360_KEYWORDS = ["insta360", "insta 360", "link 2c", "link2c", "2e1a", "4c01"]
CONFIG_DIR = os.path.expanduser("~/.config/insta360-link")
AUDIO_CONFIG = os.path.join(CONFIG_DIR, "audio_settings.json")

AUDIO_QUALITIES = [
    {"label": "High (48kHz 320kbps)", "sample_rate": 48000, "bitrate": "320k"},
    {"label": "Standard (48kHz 192kbps)", "sample_rate": 48000, "bitrate": "192k"},
    {"label": "Medium (44.1kHz 128kbps)", "sample_rate": 44100, "bitrate": "128k"},
    {"label": "Low (22kHz 96kbps)", "sample_rate": 22050, "bitrate": "96k"},
    {"label": "Voice (16kHz 64kbps)", "sample_rate": 16000, "bitrate": "64k"},
]


class VUMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedHeight(20); self.setMinimumWidth(200)
        self._level = 0.0; self._peak = 0.0; self._peak_hold = 0; self._is_clipping = False
    def set_level(self, level):
        self._level = max(0.0, min(1.0, level))
        if level > self._peak: self._peak = level; self._peak_hold = 30
        else:
            self._peak_hold -= 1
            if self._peak_hold <= 0: self._peak = max(self._peak - 0.02, self._level)
        self._is_clipping = level > 0.95; self.update()
    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setBrush(QBrush(QColor(theme.BRAND_BORDER))); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, 4, 4)
        if self._level > 0.001:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, QColor(theme.BRAND_GREEN)); grad.setColorAt(0.55, QColor(theme.BRAND_GREEN))
            grad.setColorAt(0.70, QColor(theme.BRAND_WARN)); grad.setColorAt(0.85, QColor(theme.BRAND_RED))
            grad.setColorAt(1.0, QColor("#FF1A1A")); p.setBrush(QBrush(grad))
            p.drawRoundedRect(0, 0, int(w * self._level), h, 4, 4)
        if self._peak > 0.02:
            px = max(2, min(int(w * self._peak), w - 2))
            pc = QColor(theme.BRAND_RED) if self._peak > 0.85 else (QColor(theme.BRAND_WARN) if self._peak > 0.6 else QColor(theme.BRAND_GREEN))
            p.setPen(QPen(pc, 2)); p.drawLine(px, 2, px, h - 2)
        if self._is_clipping:
            p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(QColor(theme.BRAND_RED), 2))
            p.drawRoundedRect(1, 1, w - 2, h - 2, 4, 4)
        p.end()


class PulseSource:
    def __init__(self, index, name, description, is_monitor=False):
        self.index = index; self.name = name; self.description = description; self.is_monitor = is_monitor


class AudioBackend:
    def __init__(self):
        self.source_name = None; self.source_index = None
        self.device_label = "No microphone detected"
        self.sd_device_index = None; self.all_sources = []; self.input_sources = []
        self._discover_sources()

    def _run(self, cmd):
        try:
            env = os.environ.copy()
            if os.getuid() == 0:
                real_user = env.get("SUDO_USER") or env.get("USER")
                if not real_user or real_user == "root":
                    try:
                        for e in os.listdir("/run/user"):
                            if e != "0":
                                import pwd
                                try: real_user = pwd.getpwuid(int(e)).pw_name
                                except: pass; break
                    except: pass
                if real_user and real_user != "root":
                    cmd = ["runuser", "-u", real_user, "--"] + list(cmd)
            else:
                if "XDG_RUNTIME_DIR" not in env:
                    env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
            pactl = shutil.which("pactl")
            if pactl: cmd = [pactl if c == "pactl" else c for c in cmd]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, env=env)
            return result.stdout.strip() if result.returncode == 0 else ""
        except: return ""

    def _discover_sources(self):
        self.all_sources = []; self.input_sources = []
        short = self._run(["pactl", "list", "sources", "short"])
        if not short: return
        source_names = []
        for line in short.split("\n"):
            parts = line.strip().split("\t")
            if len(parts) >= 2: source_names.append((parts[0].strip(), parts[1].strip()))
        desc_map = {}
        full = self._run(["pactl", "list", "sources"])
        if full:
            cur = None
            for line in full.split("\n"):
                s = line.strip()
                if s.startswith("Name:"): cur = s.split("Name:",1)[1].strip()
                elif s.startswith("Description:") and cur: desc_map[cur] = s.split("Description:",1)[1].strip(); cur = None
        for idx, name in source_names:
            desc = desc_map.get(name, name)
            is_mon = ".monitor" in name.lower() or "monitor of" in desc.lower()
            self.all_sources.append(PulseSource(idx, name, desc, is_mon))
        self.input_sources = [s for s in self.all_sources if not s.is_monitor]
        self._auto_select()

    def _auto_select(self):
        for src in self.input_sources:
            combined = (src.name + " " + src.description).lower()
            for kw in INSTA360_KEYWORDS:
                if kw in combined: self._select_source(src); return
        for src in self.input_sources:
            if "usb" in src.name.lower(): self._select_source(src); return
        if self.input_sources: self._select_source(self.input_sources[0])

    def _select_source(self, src):
        self.source_name = src.name; self.source_index = src.index; self.device_label = src.description

    def select_by_name(self, name):
        for src in self.input_sources:
            if src.name == name: self._select_source(src); break
        self._match_sounddevice()

    def _match_sounddevice(self):
        self.sd_device_index = None
        if not HAS_SOUNDDEVICE or not self.source_name: return
        try:
            devices = sd.query_devices()
            # Try matching by description keywords
            if self.device_label:
                words = [w.lower() for w in self.device_label.split() if len(w) > 2 and w.lower() not in ("mono","stereo","analog","digital","of")]
                for i, d in enumerate(devices):
                    if d["max_input_channels"] > 0 and words:
                        dn = d["name"].lower()
                        if all(w in dn for w in words[:2]):
                            self.sd_device_index = i; return
            # Try Insta360 keywords
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0:
                    for kw in INSTA360_KEYWORDS:
                        if kw in d["name"].lower(): self.sd_device_index = i; return
            # Try any USB
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0 and "usb" in d["name"].lower():
                    self.sd_device_index = i; return
            # Default
            default = sd.default.device
            idx = default[0] if isinstance(default, (list, tuple)) else default
            if idx is not None and idx >= 0: self.sd_device_index = idx
        except: pass

    def get_volume(self):
        if not self.source_name: return 100
        out = self._run(["pactl", "get-source-volume", self.source_name])
        m = re.search(r"(\d+)%", out)
        return int(m.group(1)) if m else 100

    def set_volume(self, pct):
        if self.source_name: self._run(["pactl", "set-source-volume", self.source_name, f"{pct}%"])

    def get_mute(self):
        if not self.source_name: return False
        return "yes" in self._run(["pactl", "get-source-mute", self.source_name]).lower()

    def set_mute(self, muted):
        if self.source_name: self._run(["pactl", "set-source-mute", self.source_name, "1" if muted else "0"])


class AudioSettings:
    def __init__(self):
        self.quality_idx = 1; self.selected_source = None; self._load()
    def _load(self):
        try:
            with open(AUDIO_CONFIG) as f: d = json.load(f)
            self.quality_idx = d.get("quality_idx", 1); self.selected_source = d.get("selected_source")
        except: pass
    def save(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(AUDIO_CONFIG, "w") as f:
                json.dump({"quality_idx": self.quality_idx, "selected_source": self.selected_source}, f, indent=2)
        except: pass
    @property
    def quality(self):
        if 0 <= self.quality_idx < len(AUDIO_QUALITIES): return AUDIO_QUALITIES[self.quality_idx]
        return AUDIO_QUALITIES[1]


class AudioTab(QWidget):
    sourceChanged = pyqtSignal()  # emitted when mic source changes

    def __init__(self, backend_v4l2):
        super().__init__()
        self.backend_v4l2 = backend_v4l2
        self.audio = AudioBackend()
        self.audio_settings = AudioSettings()
        if self.audio_settings.selected_source:
            self.audio.select_by_name(self.audio_settings.selected_source)
        self.audio._match_sounddevice()
        self._stream = None; self._current_rms = 0.0

        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0)
        self.scroll_area = QScrollArea(); self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea{border:none;background:transparent;}QWidget#ASC{background:transparent;}")
        content = QWidget(); content.setObjectName("ASC")
        layout = QVBoxLayout(content); layout.setContentsMargins(16,16,16,16); layout.setSpacing(0)

        # ── INPUT SOURCE ──
        layout.addWidget(SectionHeader("🎤", "Input Source"))
        self.source_combo = self._make_combo()
        self._populate_sources()
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        layout.addWidget(self.source_combo); layout.addSpacing(8)

        sr = QHBoxLayout(); sr.setContentsMargins(0,0,0,0); sr.setSpacing(8)
        self.dot_lbl = QLabel("●"); self.status_lbl = QLabel("")
        self._update_status_display()
        sr.addWidget(self.dot_lbl); sr.addWidget(self.status_lbl); sr.addStretch()
        btn_r = QPushButton("↻ Refresh")
        btn_r.setStyleSheet(f"border:1px solid {theme.BRAND_BORDER}; color:{theme.BRAND_TEXT_SOFT}; font-size:10px; padding:2px 8px; border-radius:4px; font-family:{theme.FONT_MONO};")
        btn_r.setCursor(Qt.CursorShape.PointingHandCursor); btn_r.clicked.connect(self._on_refresh)
        sr.addWidget(btn_r); layout.addLayout(sr); layout.addSpacing(6)

        self.t_mute, _ = make_toggle_row("Mute Microphone", False, layout)
        self.t_mute.toggled.connect(self._on_mute_toggled)

        layout.addWidget(Divider())

        # ── VOLUME ──
        layout.addWidget(SectionHeader("🔊", "Input Volume"))
        iv = self.audio.get_volume()
        self.s_volume = SliderWidget("Volume", 0, 150, iv, "%")
        self.s_volume.valueChanged.connect(self._on_vol)
        layout.addWidget(self.s_volume)
        self.lbl_db = QLabel(self._db(iv))
        self.lbl_db.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM}; font-family:{theme.FONT_MONO}; font-size:10px; margin-bottom:4px;")
        layout.addWidget(self.lbl_db)
        self.lbl_boost = QLabel("⚠  Above 100% — digital boost may add noise")
        self.lbl_boost.setStyleSheet(f"color:{theme.BRAND_WARN}; font-size:10px; font-family:{theme.FONT_MONO};")
        self.lbl_boost.setVisible(iv > 100); layout.addWidget(self.lbl_boost)

        layout.addWidget(Divider())

        # ── RECORDING QUALITY ──
        layout.addWidget(SectionHeader("🎚️", "Recording Quality"))
        layout.addWidget(QLabel("AUDIO QUALITY"))
        self.quality_combo = self._make_combo()
        for q in AUDIO_QUALITIES: self.quality_combo.addItem(q["label"])
        self.quality_combo.setCurrentIndex(self.audio_settings.quality_idx)
        self.quality_combo.currentIndexChanged.connect(self._on_quality)
        layout.addWidget(self.quality_combo); layout.addSpacing(6)
        self.lbl_qi = QLabel(""); self.lbl_qi.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM}; font-size:10px; font-family:{theme.FONT_MONO};")
        self._update_qi(); layout.addWidget(self.lbl_qi)

        layout.addWidget(Divider())

        # ── LEVEL METER ──
        layout.addWidget(SectionHeader("📊", "Level Meter"))
        self.meter = VUMeter(); layout.addWidget(self.meter); layout.addSpacing(6)
        mi = QHBoxLayout(); mi.setContentsMargins(0,0,0,0)
        self.lbl_rms = QLabel("-∞ dBFS"); self.lbl_rms.setStyleSheet(f"color:{theme.BRAND_TEXT_SOFT}; font-family:{theme.FONT_MONO}; font-size:11px;")
        mi.addWidget(self.lbl_rms); mi.addStretch()
        self.lbl_peak = QLabel(""); self.lbl_peak.setStyleSheet(f"color:{theme.BRAND_RED}; font-family:{theme.FONT_MONO}; font-size:10px; font-weight:bold;")
        mi.addWidget(self.lbl_peak); layout.addLayout(mi); layout.addSpacing(8)
        sc = QHBoxLayout(); sc.setContentsMargins(0,0,0,0)
        for l in ["-60","-40","-20","-12","-6","-3","0"]:
            lb = QLabel(l); lb.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM}; font-family:{theme.FONT_MONO}; font-size:9px;")
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter); sc.addWidget(lb)
        layout.addLayout(sc)

        layout.addWidget(Divider())
        layout.addWidget(SectionHeader("💡", "Info"))
        lh = QLabel("Volume controlled via PulseAudio/PipeWire. Recording quality applies when recording video with audio.")
        lh.setWordWrap(True); lh.setStyleSheet(f"color:{theme.BRAND_TEXT_SOFT}; font-size:10px; font-family:{theme.FONT_MONO};")
        layout.addWidget(lh)
        if not HAS_SOUNDDEVICE:
            li = QLabel("⚠  Install sounddevice for live meter:\n  Arch: yay -S python-sounddevice\n  Ubuntu: sudo apt install python3-sounddevice")
            li.setStyleSheet(f"color:{theme.BRAND_WARN}; font-size:10px; font-family:{theme.FONT_MONO};")
            layout.addWidget(li)

        layout.addStretch(); self.scroll_area.setWidget(content); main_layout.addWidget(self.scroll_area)
        self._mt = QTimer(); self._mt.timeout.connect(self._update_meter)
        self._start_stream()

    def _make_combo(self):
        c = QComboBox()
        c.setStyleSheet(f"QComboBox{{background-color:{theme.BRAND_DARK};border:1px solid {theme.BRAND_BORDER};border-radius:6px;padding:6px 10px;color:{theme.BRAND_TEXT};font-family:{theme.FONT_MONO};font-size:11px;min-width:0px;}}QComboBox:focus{{border:1px solid {theme.BRAND_CYAN};}}QComboBox::drop-down{{border:none;}}QComboBox QAbstractItemView{{background-color:{theme.BRAND_CARD};border:1px solid {theme.BRAND_BORDER};color:{theme.BRAND_TEXT};selection-background-color:rgba(0,212,170,48);font-family:{theme.FONT_MONO};font-size:11px;}}")
        return c

    def _populate_sources(self):
        self.source_combo.blockSignals(True); self.source_combo.clear(); si = 0
        if self.audio.input_sources:
            self.source_combo.setDisabled(False)
            for i, src in enumerate(self.audio.input_sources):
                combined = (src.name + " " + src.description).lower()
                is_insta = any(kw in combined for kw in INSTA360_KEYWORDS)
                label = f"📷 {src.description or src.name}" if is_insta else (src.description or src.name)
                self.source_combo.addItem(label, src.name)
                if src.name == self.audio.source_name: si = i
            self.source_combo.setCurrentIndex(si)
        else: self.source_combo.addItem("No input sources found"); self.source_combo.setDisabled(True)
        self.source_combo.blockSignals(False)

    def _update_status_display(self):
        if self.audio.source_name:
            self.dot_lbl.setStyleSheet(f"color:{theme.BRAND_GREEN}; font-size:12px;")
            self.status_lbl.setText(self.audio.device_label or "Active")
            self.status_lbl.setStyleSheet(f"color:{theme.BRAND_GREEN}; font-size:10px; font-family:{theme.FONT_MONO}; font-weight:600;")
        else:
            self.dot_lbl.setStyleSheet(f"color:{theme.BRAND_RED}; font-size:12px;")
            self.status_lbl.setText("No source")
            self.status_lbl.setStyleSheet(f"color:{theme.BRAND_RED}; font-size:10px; font-family:{theme.FONT_MONO}; font-weight:600;")

    def _update_qi(self):
        q = self.audio_settings.quality
        self.lbl_qi.setText(f"Sample rate: {q['sample_rate']} Hz  ·  Bitrate: {q['bitrate']}")

    def _on_source_changed(self, idx):
        if idx < 0 or idx >= len(self.audio.input_sources): return
        src = self.audio.input_sources[idx]
        self.audio.select_by_name(src.name)
        self.audio_settings.selected_source = src.name; self.audio_settings.save()
        self._update_status_display()
        # Restart VU meter with new device
        self._stop_stream(); self._start_stream()
        self.s_volume.set_value(self.audio.get_volume())
        # Notify preview about source change
        self.sourceChanged.emit()

    def _on_refresh(self):
        old = self.audio.source_name
        self.audio._discover_sources(); self.audio._match_sounddevice()
        self._populate_sources(); self._update_status_display()
        if self.audio.source_name != old:
            self._stop_stream(); self._start_stream()
            self.sourceChanged.emit()

    def _on_quality(self, idx):
        self.audio_settings.quality_idx = idx; self.audio_settings.save(); self._update_qi()

    def _db(self, pct):
        if pct <= 0: return "-∞ dB"
        return f"{20*math.log10(pct/100):+.1f} dB"

    def _on_vol(self, v):
        self.audio.set_volume(v); self.lbl_db.setText(self._db(v)); self.lbl_boost.setVisible(v > 100)

    def _on_mute_toggled(self, muted):
        self.audio.set_mute(muted)
        if muted:
            self.meter.set_level(0.0); self.lbl_rms.setText("MUTED")
            self.lbl_rms.setStyleSheet(f"color:{theme.BRAND_RED}; font-family:{theme.FONT_MONO}; font-size:11px; font-weight:bold;")
        else:
            self.lbl_rms.setStyleSheet(f"color:{theme.BRAND_TEXT_SOFT}; font-family:{theme.FONT_MONO}; font-size:11px;")

    def _start_stream(self):
        if not HAS_SOUNDDEVICE or self.audio.sd_device_index is None:
            self.lbl_rms.setText("No input stream"); return
        try:
            dev = sd.query_devices(self.audio.sd_device_index)
            native = int(dev.get("default_samplerate", 48000))
        except: native = 48000
        for rate in list(dict.fromkeys([native, 48000, 44100, 16000])):
            try:
                self._stream = sd.InputStream(device=self.audio.sd_device_index, channels=1,
                    samplerate=rate, blocksize=1024, dtype='float32', callback=self._acb)
                self._stream.start(); self._mt.start(50); return
            except: continue
        self.lbl_rms.setText("Stream error")

    def _stop_stream(self):
        self._mt.stop()
        if self._stream:
            try: self._stream.stop(); self._stream.close()
            except: pass
            self._stream = None

    def _acb(self, indata, frames, ti, status):
        if indata is not None and len(indata) > 0:
            self._current_rms = float(np.sqrt(np.mean(indata**2)))

    def _update_meter(self):
        if self.t_mute._checked: return
        rms = self._current_rms
        if rms > 0.00001: db = 20*math.log10(rms); norm = max(0, min(1, (db+60)/60))
        else: db = -99; norm = 0
        self.meter.set_level(norm)
        self.lbl_rms.setText("-∞ dBFS" if db < -60 else f"{db:.1f} dBFS")
        if norm > 0.95: self.lbl_peak.setText("⬤ CLIP"); self.lbl_peak.setStyleSheet(f"color:{theme.BRAND_RED}; font-family:{theme.FONT_MONO}; font-size:10px; font-weight:bold;")
        elif norm > 0.80: self.lbl_peak.setText("⬤ PEAK"); self.lbl_peak.setStyleSheet(f"color:{theme.BRAND_WARN}; font-family:{theme.FONT_MONO}; font-size:10px; font-weight:bold;")
        else: self.lbl_peak.setText("")

    def stop_stream(self): self._stop_stream()
