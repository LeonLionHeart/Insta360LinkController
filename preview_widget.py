#!/usr/bin/env python3
# preview_widget.py

import os
import cv2
import shutil
import subprocess
import threading
import queue
from datetime import datetime
from PyQt6.QtWidgets import (QLabel, QVBoxLayout, QHBoxLayout, QWidget, QPushButton)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QPropertyAnimation, pyqtProperty, QEasingCurve
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QLinearGradient, QBrush
import theme
from bg_engine import VirtualBackgroundEngine


class PulsingDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedSize(8, 8); self._opacity = 1.0
        self._anim = QPropertyAnimation(self, b"dot_opacity", self)
        self._anim.setDuration(1000); self._anim.setStartValue(1.0); self._anim.setEndValue(0.3)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine); self._anim.setLoopCount(-1)
    @pyqtProperty(float)
    def dot_opacity(self): return self._opacity
    @dot_opacity.setter
    def dot_opacity(self, v): self._opacity = v; self.update()
    def start(self): self._anim.start()
    def stop(self): self._anim.stop(); self._opacity = 1.0
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._opacity); p.setBrush(QBrush(QColor(theme.BRAND_RED)))
        p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(0, 0, 8, 8); p.end()

class OverlayButton(QPushButton):
    def __init__(self, text, size=36, parent=None):
        super().__init__(text, parent); self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{ background-color:rgba(17,24,32,200); border:1.5px solid {theme.BRAND_BORDER};
                border-radius:{size//2}px; color:{theme.BRAND_TEXT}; font-size:16px; padding:0; }}
            QPushButton:hover {{ background-color:rgba(17,24,32,255); border-color:rgba(0,212,170,100); }}
        """)

class RecordButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedSize(44, 44)
        self.setCursor(Qt.CursorShape.PointingHandCursor); self._recording = False
        self.setStyleSheet("background:transparent; border:none;")
    def set_recording(self, r): self._recording = r; self.update()
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(theme.BRAND_RED) if self._recording else QColor("#FFF")
        p.setPen(QPen(c, 2))
        p.setBrush(QBrush(QColor(theme.BRAND_RED)) if self._recording else Qt.BrushStyle.NoBrush)
        p.drawEllipse(2, 2, 40, 40); p.setPen(Qt.PenStyle.NoPen)
        if self._recording:
            p.setBrush(QBrush(QColor("#FFF"))); p.drawRoundedRect(15, 15, 14, 14, 2, 2)
        else:
            p.setBrush(QBrush(QColor(theme.BRAND_RED))); p.drawEllipse(11, 11, 22, 22)
        p.end()


def _get_real_user():
    if os.getuid() != 0: return None
    u = os.environ.get("SUDO_USER")
    if u and u != "root": return u
    try:
        for e in os.listdir("/run/user"):
            if e != "0":
                import pwd
                try: return pwd.getpwuid(int(e)).pw_name
                except: pass
    except: pass
    return None


class RecordingPipeline:
    def __init__(self):
        self._proc = None; self._write_thread = None
        self._frame_queue = queue.Queue(maxsize=10); self._running = False; self.filepath = ""

    def start(self, filepath, width, height, fps, pulse_source=None, audio_bitrate="192k"):
        self.filepath = filepath
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg: return False
        cmd = []
        real_user = _get_real_user()
        if real_user: cmd = ["runuser", "-u", real_user, "--"]
        has_audio = pulse_source is not None
        if has_audio:
            cmd += [ffmpeg, "-y", "-f", "pulse", "-i", pulse_source,
                    "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0",
                    "-map", "1:v", "-map", "0:a", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                    "-c:a", "aac", "-b:a", audio_bitrate, "-shortest", filepath]
        else:
            cmd += [ffmpeg, "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                    "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", filepath]
        try:
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, bufsize=width*height*3*2)
        except: return False
        self._running = True
        self._write_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._write_thread.start(); return True

    def write_frame(self, frame):
        if not self._running: return
        try: self._frame_queue.put_nowait(frame.tobytes())
        except queue.Full: pass

    def _writer_loop(self):
        while self._running:
            try: data = self._frame_queue.get(timeout=0.1)
            except queue.Empty: continue
            try:
                if self._proc and self._proc.stdin: self._proc.stdin.write(data)
            except (BrokenPipeError, OSError): self._running = False; break

    def stop(self):
        self._running = False
        while not self._frame_queue.empty():
            try: self._frame_queue.get_nowait()
            except: break
        if self._proc:
            try: self._proc.stdin.close()
            except: pass
            try: self._proc.wait(timeout=10)
            except:
                try: self._proc.kill()
                except: pass
            self._proc = None
        if self._write_thread: self._write_thread.join(timeout=3); self._write_thread = None


class CameraPreview(QWidget):
    recordingToggled = pyqtSignal(bool)
    micToggled = pyqtSignal(bool)
    snapshotTaken = pyqtSignal(str)
    recordingStopped = pyqtSignal(str)

    def __init__(self, device="/dev/video0"):
        super().__init__()
        self.device = device; self.capture = None
        self._recording = False; self._mic_muted = False; self._zoom_level = 100
        self._res_text = "1920×1080 @ 30fps"; self._has_feed = False
        self._virtual_camera = None; self._lut_fn = None
        self._mirror_h = False; self._flip_v = False
        self._current_frame = None
        self._frame_w = 1920; self._frame_h = 1080; self._frame_fps = 30
        self._file_settings = None; self._audio_settings = None; self._audio_backend = None
        self._recorder = None; self._record_start = None; self._record_path = ""
        self._vcam_queue = queue.Queue(maxsize=3)
        self._vcam_thread = None; self._vcam_running = False

        # Virtual Background Engine
        self.bg_engine = VirtualBackgroundEngine()

        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(0,0,0,0); main_layout.setSpacing(0)
        self.container = QWidget()
        self.container.setStyleSheet(f"background-color:#000; border:1px solid {theme.BRAND_BORDER}; border-radius:12px;")
        cl = QVBoxLayout(self.container); cl.setContentsMargins(0,0,0,0)
        self.video_label = QLabel(); self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background:transparent;")
        cl.addWidget(self.video_label); main_layout.addWidget(self.container)
        self.timer = QTimer(); self.timer.timeout.connect(self.update_frame)
        self.container.paintEvent = self._paint_overlays
        self._build_overlays()
        self._rec_timer = QTimer(); self._rec_timer.timeout.connect(self._update_rec_time)

    def set_file_settings(self, s): self._file_settings = s
    def set_audio_settings(self, audio_settings, audio_backend):
        self._audio_settings = audio_settings; self._audio_backend = audio_backend
    def set_virtual_camera(self, v): self._virtual_camera = v
    def set_lut(self, fn): self._lut_fn = fn
    def set_mirror(self, e): self._mirror_h = e
    def set_flip(self, e): self._flip_v = e

    def set_virtual_background(self, mode, path=""):
        import sys
        print(f"[preview] set_virtual_background({mode!r}, {path!r}), engine={self.bg_engine is not None}, avail={self.bg_engine._available if self.bg_engine else 'N/A'}", file=sys.stderr)
        if self.bg_engine: self.bg_engine.set_mode(mode, path)

    def set_bg_blur_strength(self, strength):
        if self.bg_engine: self.bg_engine.set_blur_strength(strength)

    def _build_overlays(self):
        self.btn_record = RecordButton(self.container)
        self.btn_record.clicked.connect(self._toggle_recording)
        self.btn_snapshot = OverlayButton("📸", 36, self.container)
        self.btn_snapshot.setToolTip("Take Snapshot"); self.btn_snapshot.clicked.connect(self._take_snapshot)
        self.btn_mic = OverlayButton("🎤", 36, self.container)
        self.btn_mic.setToolTip("Toggle Mic"); self.btn_mic.clicked.connect(self._toggle_mic)
        self.rec_time_lbl = QLabel("", self.container)
        self.rec_time_lbl.setStyleSheet(
            f"background-color:rgba(255,71,87,50); color:{theme.BRAND_RED}; "
            f"font-family:{theme.FONT_MONO}; font-size:11px; font-weight:700; border-radius:6px; padding:4px 10px;")
        self.rec_time_lbl.hide()
        self.rec_dot = PulsingDot(self.container); self.rec_dot.hide()
        self.zoom_badge = QLabel("1.0×", self.container)
        self.zoom_badge.setStyleSheet(
            f"background-color:rgba(17,24,32,220); border-radius:6px; padding:4px 10px; "
            f"color:{theme.BRAND_CYAN}; font-family:{theme.FONT_MONO}; font-size:11px; font-weight:700;")
        self.zoom_badge.hide()
        self.flash_overlay = QLabel(self.container)
        self.flash_overlay.setStyleSheet("background-color:rgba(255,255,255,180); border-radius:12px;")
        self.flash_overlay.hide()
        self.toast_lbl = QLabel(self.container)
        self.toast_lbl.setStyleSheet(
            f"background-color:rgba(0,212,170,200); color:#000; font-family:{theme.FONT_MONO}; "
            f"font-size:10px; font-weight:700; border-radius:6px; padding:6px 12px;")
        self.toast_lbl.hide()
        self.placeholder_icon = QLabel("📷", self.container)
        self.placeholder_icon.setAlignment(Qt.AlignmentFlag.AlignCenter); self.placeholder_icon.setStyleSheet("font-size:48px;")
        self.placeholder_text = QLabel("Live Preview", self.container)
        self.placeholder_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_text.setStyleSheet(f"color:{theme.BRAND_TEXT_SOFT}; font-family:{theme.FONT_MONO}; font-size:13px;")
        self.res_label = QLabel(self._res_text, self.container)
        self.res_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.res_label.setStyleSheet(f"color:{theme.BRAND_TEXT_DIM}; font-family:{theme.FONT_MONO}; font-size:10px;")

    def resizeEvent(self, e): super().resizeEvent(e); self._pos()
    def _pos(self):
        w, h = self.container.width(), self.container.height()
        by = h - 55; cx = w // 2
        self.btn_record.move(cx-22, by); self.btn_snapshot.move(cx+32, by+4); self.btn_mic.move(cx-68, by+4)
        self.rec_time_lbl.adjustSize(); rw = self.rec_time_lbl.width()
        self.rec_time_lbl.move(w-rw-12, 12); self.rec_dot.move(w-rw-24, 20)
        self.zoom_badge.adjustSize(); self.zoom_badge.move(w-self.zoom_badge.width()-12, h-70)
        self.flash_overlay.setGeometry(0,0,w,h); self.toast_lbl.move(12, h-70)
        self.placeholder_icon.setFixedWidth(w); self.placeholder_icon.move(0, h//2-50)
        self.placeholder_text.setFixedWidth(w); self.placeholder_text.move(0, h//2+5)
        self.res_label.setFixedWidth(w); self.res_label.move(0, h//2+25)

    def _paint_overlays(self, event):
        QWidget.paintEvent(self.container, event)
        p = QPainter(self.container); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.container.width(), self.container.height()
        cc = QColor(theme.BRAND_CYAN); cc.setAlpha(48); p.setPen(QPen(cc, 1))
        cx, cy = w//2, h//2; p.drawLine(cx,cy-20,cx,cy+20); p.drawLine(cx-20,cy,cx+20,cy)
        grad = QLinearGradient(0,h-80,0,h); grad.setColorAt(0,QColor(0,0,0,0)); grad.setColorAt(1,QColor(0,0,0,178))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(grad)); p.drawRect(0,h-80,w,80); p.end()

    def set_zoom_display(self, v):
        self._zoom_level = v
        if v > 100: self.zoom_badge.setText(f"{v/100:.1f}×"); self.zoom_badge.adjustSize(); self.zoom_badge.show()
        else: self.zoom_badge.hide()
        self._pos()

    def set_resolution_text(self, w, h, fps):
        self._res_text = f"{w}×{h} @ {fps}fps"; self.res_label.setText(self._res_text)
        self._frame_w = w; self._frame_h = h; self._frame_fps = fps

    # ── VCam thread ──
    def _start_vcam_thread(self):
        if self._vcam_thread and self._vcam_running: return
        self._vcam_running = True
        self._vcam_thread = threading.Thread(target=self._vcam_loop, daemon=True); self._vcam_thread.start()
    def _vcam_loop(self):
        while self._vcam_running:
            try: frame = self._vcam_queue.get(timeout=0.1)
            except queue.Empty: continue
            vcam = self._virtual_camera
            if vcam and vcam.is_active: vcam.feed_frame(frame)
    def _stop_vcam_thread(self):
        self._vcam_running = False
        if self._vcam_thread: self._vcam_thread.join(timeout=2); self._vcam_thread = None

    # ── Recording ──
    def _make_filename(self, directory, ext, prefix="recording"):
        os.makedirs(directory, exist_ok=True)
        if self._file_settings and self._file_settings.timestamp_names:
            return os.path.join(directory, f"{prefix}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}{ext}")
        i = 1
        while True:
            path = os.path.join(directory, f"{prefix}_{i:04d}{ext}")
            if not os.path.exists(path): return path
            i += 1

    def _toggle_recording(self):
        if self._recording: self._stop_recording()
        else: self._start_recording()

    def _start_recording(self):
        if not self._has_feed: return
        fs = self._file_settings
        directory = fs.video_dir if fs else os.path.expanduser("~/Videos")
        filepath = self._make_filename(directory, ".mp4", "recording")
        pulse_source = None
        if self._audio_backend and self._audio_backend.source_name and not self._mic_muted:
            pulse_source = self._audio_backend.source_name
        bitrate = "192k"
        if self._audio_settings: bitrate = self._audio_settings.quality.get("bitrate", "192k")
        self._recorder = RecordingPipeline()
        if not self._recorder.start(filepath, self._frame_w, self._frame_h, self._frame_fps, pulse_source, bitrate):
            self._recorder = None; return
        self._recording = True; self._record_path = filepath
        self._record_start = datetime.now()
        self.btn_record.set_recording(True)
        self.rec_time_lbl.setText("● REC 00:00"); self.rec_time_lbl.adjustSize()
        self.rec_time_lbl.show(); self.rec_dot.show(); self.rec_dot.start()
        self._rec_timer.start(1000); self._pos()
        self.recordingToggled.emit(True)

    def _stop_recording(self):
        self._recording = False; self._rec_timer.stop()
        self.btn_record.set_recording(False); self.rec_time_lbl.hide(); self.rec_dot.hide(); self.rec_dot.stop()
        if self._recorder: self._recorder.stop(); self._recorder = None
        if self._record_path:
            self.recordingStopped.emit(self._record_path)
            self._show_toast(f"Saved: {os.path.basename(self._record_path)}")
            if self._file_settings and self._file_settings.auto_open_folder:
                subprocess.Popen(["xdg-open", os.path.dirname(self._record_path)])
        self.recordingToggled.emit(False)

    def _update_rec_time(self):
        if self._record_start:
            e = (datetime.now() - self._record_start).total_seconds()
            self.rec_time_lbl.setText(f"● REC {int(e)//60:02d}:{int(e)%60:02d}")
            self.rec_time_lbl.adjustSize(); self._pos()

    # ── Snapshot ──
    def _take_snapshot(self):
        if self._current_frame is None: return
        fs = self._file_settings
        if fs: pf = fs.photo_format; directory = fs.photo_dir
        else: directory = os.path.expanduser("~/Pictures"); pf = {"ext": ".png"}
        filepath = self._make_filename(directory, pf["ext"], "snapshot")
        try:
            params = []
            if pf["ext"] == ".jpg": params = [cv2.IMWRITE_JPEG_QUALITY, pf.get("quality", 95)]
            elif pf["ext"] == ".webp": params = [cv2.IMWRITE_WEBP_QUALITY, pf.get("quality", 90)]
            cv2.imwrite(filepath, self._current_frame, params if params else None)
            self.snapshotTaken.emit(filepath); self._show_toast(f"📸 {os.path.basename(filepath)}")
            self.flash_overlay.show(); QTimer.singleShot(80, self.flash_overlay.hide)
            if fs and fs.auto_open_folder: subprocess.Popen(["xdg-open", os.path.dirname(filepath)])
        except: pass

    def _show_toast(self, t):
        self.toast_lbl.setText(t); self.toast_lbl.adjustSize(); self.toast_lbl.show()
        QTimer.singleShot(3000, self.toast_lbl.hide)

    # ── Mic ──
    def _toggle_mic(self):
        self._mic_muted = not self._mic_muted
        if self._mic_muted:
            self.btn_mic.setText("🔇")
            self.btn_mic.setStyleSheet(f"QPushButton{{background-color:rgba(17,24,32,200);border:1.5px solid {theme.BRAND_RED};border-radius:18px;color:{theme.BRAND_RED};font-size:16px;padding:0;}}QPushButton:hover{{background-color:rgba(17,24,32,255);}}")
        else:
            self.btn_mic.setText("🎤")
            self.btn_mic.setStyleSheet(f"QPushButton{{background-color:rgba(17,24,32,200);border:1.5px solid {theme.BRAND_BORDER};border-radius:18px;color:{theme.BRAND_TEXT};font-size:16px;padding:0;}}QPushButton:hover{{background-color:rgba(17,24,32,255);border-color:rgba(0,212,170,100);}}")
        self.micToggled.emit(self._mic_muted)

    # ── Camera lifecycle ──
    def start(self, device=None, width=1920, height=1080, fps=30):
        if device: self.device = device
        self.stop(); self.set_resolution_text(width, height, fps)
        self.capture = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.capture.set(cv2.CAP_PROP_FPS, fps)
        if self.capture.isOpened():
            self.timer.start(int(1000/fps) if fps > 0 else 33)
            self._has_feed = True
            self.placeholder_icon.hide(); self.placeholder_text.hide(); self.res_label.hide()
            self._start_vcam_thread()
        else:
            self._has_feed = False; self.placeholder_icon.show()
            self.placeholder_text.setText(f"Failed to open {self.device}\n\nIs it in use?")
            self.placeholder_text.setStyleSheet(f"color:{theme.BRAND_RED};font-family:{theme.FONT_MONO};font-size:12px;font-weight:bold;")
            self.placeholder_text.show()

    def stop(self):
        if self._recording: self._stop_recording()
        self._stop_vcam_thread(); self.timer.stop()
        if self.capture and self.capture.isOpened(): self.capture.release()
        self._has_feed = False; self.video_label.clear()
        self.placeholder_icon.show(); self.placeholder_text.show(); self.res_label.show()

    def shutdown(self):
        """Call on app close to release all resources including bg engine."""
        self.stop()
        if self.bg_engine: self.bg_engine.release()

    def update_frame(self):
        if not self.capture or not self.capture.isOpened(): return
        ret, frame = self.capture.read()
        if not ret: return

        # 1. Flip/mirror
        if self._mirror_h and self._flip_v: frame = cv2.flip(frame, -1)
        elif self._mirror_h: frame = cv2.flip(frame, 1)
        elif self._flip_v: frame = cv2.flip(frame, 0)

        # 2. Apply LUT
        processed = self._lut_fn(frame) if self._lut_fn else frame

        # 3. Apply virtual background
        if self.bg_engine and self.bg_engine.mode != "none":
            processed = self.bg_engine.process_frame(processed)

        self._current_frame = processed

        # 4. Write to recording (non-blocking)
        if self._recording and self._recorder:
            self._recorder.write_frame(processed)

        # 5. Feed virtual camera (non-blocking)
        vcam = self._virtual_camera
        if vcam and vcam.is_active:
            try: self._vcam_queue.put_nowait(processed)
            except queue.Full: pass

        # 6. Scale down for display — use container size (Gemini's fix)
        dw = self.container.width()
        dh = self.container.height()
        if dw < 10 or dh < 10: dw, dh = 640, 360

        fh, fw = processed.shape[:2]
        scale = min(dw / fw, dh / fh)
        sw = max(1, int(fw * scale))
        sh = max(1, int(fh * scale))

        if scale < 0.95:
            small = cv2.resize(processed, (sw, sh), interpolation=cv2.INTER_LINEAR)
        else:
            small = processed

        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        # .copy() prevents numpy array garbage collection under QImage (Gemini's fix)
        q = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888).copy()
        self.video_label.setPixmap(QPixmap.fromImage(q))
