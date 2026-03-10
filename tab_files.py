#!/usr/bin/env python3
# tab_files.py

import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QScrollArea, QFrame, QComboBox,
                             QFileDialog, QLineEdit)
from PyQt6.QtCore import Qt, pyqtSignal
from ui_widgets import SectionHeader, Divider, make_toggle_row
import theme

CONFIG_DIR = os.path.expanduser("~/.config/insta360-link")
FILES_CONFIG = os.path.join(CONFIG_DIR, "file_settings.json")

# Resolve real home even when running as root via sudo
_REAL_HOME = os.path.expanduser(f"~{os.environ.get('SUDO_USER', '')}" if os.getuid() == 0 else "~")

VIDEO_FORMATS = [
    {"label": "MP4 (H.264)", "ext": ".mp4", "fourcc": "mp4v", "container": "mp4"},
    {"label": "MKV (H.264)", "ext": ".mkv", "fourcc": "X264", "container": "mkv"},
    {"label": "AVI (MJPEG)", "ext": ".avi", "fourcc": "MJPG", "container": "avi"},
    {"label": "AVI (XVID)", "ext": ".avi", "fourcc": "XVID", "container": "avi"},
    {"label": "WebM (VP8)", "ext": ".webm", "fourcc": "VP80", "container": "webm"},
]

PHOTO_FORMATS = [
    {"label": "PNG (Lossless)", "ext": ".png"},
    {"label": "JPEG (Quality 95)", "ext": ".jpg", "quality": 95},
    {"label": "JPEG (Quality 80)", "ext": ".jpg", "quality": 80},
    {"label": "WebP (Quality 90)", "ext": ".webp", "quality": 90},
    {"label": "BMP (Uncompressed)", "ext": ".bmp"},
]

DEFAULTS = {
    "video_dir": os.path.join(_REAL_HOME, "Videos"),
    "photo_dir": os.path.join(_REAL_HOME, "Pictures"),
    "video_format_idx": 0,
    "photo_format_idx": 0,
    "auto_open_folder": False,
    "timestamp_names": True,
}


class FileSettings:
    """Persistent file location / format settings."""

    def __init__(self):
        self.video_dir = DEFAULTS["video_dir"]
        self.photo_dir = DEFAULTS["photo_dir"]
        self.video_format_idx = DEFAULTS["video_format_idx"]
        self.photo_format_idx = DEFAULTS["photo_format_idx"]
        self.auto_open_folder = DEFAULTS["auto_open_folder"]
        self.timestamp_names = DEFAULTS["timestamp_names"]
        self._load()

    def _load(self):
        try:
            with open(FILES_CONFIG, "r") as f:
                d = json.load(f)
            self.video_dir = d.get("video_dir", self.video_dir)
            self.photo_dir = d.get("photo_dir", self.photo_dir)
            self.video_format_idx = d.get("video_format_idx", self.video_format_idx)
            self.photo_format_idx = d.get("photo_format_idx", self.photo_format_idx)
            self.auto_open_folder = d.get("auto_open_folder", self.auto_open_folder)
            self.timestamp_names = d.get("timestamp_names", self.timestamp_names)
        except Exception:
            pass

    def save(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(FILES_CONFIG, "w") as f:
                json.dump({
                    "video_dir": self.video_dir,
                    "photo_dir": self.photo_dir,
                    "video_format_idx": self.video_format_idx,
                    "photo_format_idx": self.photo_format_idx,
                    "auto_open_folder": self.auto_open_folder,
                    "timestamp_names": self.timestamp_names,
                }, f, indent=2)
        except Exception:
            pass

    @property
    def video_format(self):
        if 0 <= self.video_format_idx < len(VIDEO_FORMATS):
            return VIDEO_FORMATS[self.video_format_idx]
        return VIDEO_FORMATS[0]

    @property
    def photo_format(self):
        if 0 <= self.photo_format_idx < len(PHOTO_FORMATS):
            return PHOTO_FORMATS[self.photo_format_idx]
        return PHOTO_FORMATS[0]


class PathSelector(QWidget):
    """Directory selector with display and browse button."""
    pathChanged = pyqtSignal(str)

    def __init__(self, current_path, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.path_label = QLineEdit(current_path)
        self.path_label.setReadOnly(True)
        self.path_label.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.BRAND_DARK};
                border: 1px solid {theme.BRAND_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                color: {theme.BRAND_TEXT};
                font-family: {theme.FONT_MONO};
                font-size: 10px;
            }}
        """)
        layout.addWidget(self.path_label, stretch=1)

        btn_browse = QPushButton("Browse")
        btn_browse.setStyleSheet(
            f"border: 1px solid {theme.BRAND_BORDER}; color: {theme.BRAND_TEXT_SOFT}; "
            f"font-size: 10px; padding: 5px 12px; border-radius: 5px; "
            f"font-family: {theme.FONT_MONO};"
        )
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.clicked.connect(self._browse)
        layout.addWidget(btn_browse)

        btn_open = QPushButton("📂")
        btn_open.setFixedSize(28, 28)
        btn_open.setToolTip("Open folder")
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {theme.BRAND_BORDER};
                border-radius: 6px; font-size: 14px; padding: 0;
            }}
            QPushButton:hover {{ border-color: rgba(0, 212, 170, 96); }}
        """)
        btn_open.clicked.connect(self._open_folder)
        layout.addWidget(btn_open)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Directory", self.path_label.text()
        )
        if path:
            self.path_label.setText(path)
            self.pathChanged.emit(path)

    def _open_folder(self):
        path = self.path_label.text()
        if os.path.isdir(path):
            import subprocess
            subprocess.Popen(["xdg-open", path])

    def set_path(self, path):
        self.path_label.setText(path)


class FilesTab(QWidget):
    settingsChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.settings = FileSettings()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QWidget#FilesScrollContent { background: transparent; }
        """)

        content = QWidget()
        content.setObjectName("FilesScrollContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        # ── VIDEO RECORDING ──
        layout.addWidget(SectionHeader("🎬", "Video Recording"))

        lbl_vid_dir = QLabel("SAVE LOCATION")
        lbl_vid_dir.setStyleSheet(
            f"color: {theme.BRAND_TEXT_SOFT}; font-size: 10px; "
            f"font-family: {theme.FONT_MONO}; letter-spacing: 0.5px; "
            f"font-weight: 600; margin-bottom: 6px;"
        )
        layout.addWidget(lbl_vid_dir)

        self.vid_path = PathSelector(self.settings.video_dir)
        self.vid_path.pathChanged.connect(self._on_video_dir_changed)
        layout.addWidget(self.vid_path)
        layout.addSpacing(12)

        lbl_vid_fmt = QLabel("FORMAT")
        lbl_vid_fmt.setStyleSheet(
            f"color: {theme.BRAND_TEXT_SOFT}; font-size: 10px; "
            f"font-family: {theme.FONT_MONO}; letter-spacing: 0.5px; "
            f"font-weight: 600; margin-bottom: 6px;"
        )
        layout.addWidget(lbl_vid_fmt)

        self.vid_format_combo = self._make_combo()
        for vf in VIDEO_FORMATS:
            self.vid_format_combo.addItem(vf["label"])
        self.vid_format_combo.setCurrentIndex(self.settings.video_format_idx)
        self.vid_format_combo.currentIndexChanged.connect(self._on_video_format_changed)
        layout.addWidget(self.vid_format_combo)
        layout.addSpacing(6)

        # Video info
        vf = self.settings.video_format
        self.lbl_vid_info = QLabel(f"Extension: {vf['ext']}  ·  Codec: {vf['fourcc']}")
        self.lbl_vid_info.setStyleSheet(
            f"color: {theme.BRAND_TEXT_DIM}; font-size: 10px; font-family: {theme.FONT_MONO};"
        )
        layout.addWidget(self.lbl_vid_info)

        layout.addWidget(Divider())

        # ── PHOTO CAPTURE ──
        layout.addWidget(SectionHeader("📸", "Photo Capture"))

        lbl_pic_dir = QLabel("SAVE LOCATION")
        lbl_pic_dir.setStyleSheet(
            f"color: {theme.BRAND_TEXT_SOFT}; font-size: 10px; "
            f"font-family: {theme.FONT_MONO}; letter-spacing: 0.5px; "
            f"font-weight: 600; margin-bottom: 6px;"
        )
        layout.addWidget(lbl_pic_dir)

        self.pic_path = PathSelector(self.settings.photo_dir)
        self.pic_path.pathChanged.connect(self._on_photo_dir_changed)
        layout.addWidget(self.pic_path)
        layout.addSpacing(12)

        lbl_pic_fmt = QLabel("FORMAT")
        lbl_pic_fmt.setStyleSheet(
            f"color: {theme.BRAND_TEXT_SOFT}; font-size: 10px; "
            f"font-family: {theme.FONT_MONO}; letter-spacing: 0.5px; "
            f"font-weight: 600; margin-bottom: 6px;"
        )
        layout.addWidget(lbl_pic_fmt)

        self.pic_format_combo = self._make_combo()
        for pf in PHOTO_FORMATS:
            self.pic_format_combo.addItem(pf["label"])
        self.pic_format_combo.setCurrentIndex(self.settings.photo_format_idx)
        self.pic_format_combo.currentIndexChanged.connect(self._on_photo_format_changed)
        layout.addWidget(self.pic_format_combo)

        layout.addWidget(Divider())

        # ── OPTIONS ──
        layout.addWidget(SectionHeader("⚙️", "Options"))

        self.t_timestamp, _ = make_toggle_row(
            "Timestamp filenames", self.settings.timestamp_names, layout
        )
        self.t_timestamp.toggled.connect(self._on_timestamp_toggled)

        self.t_open_folder, _ = make_toggle_row(
            "Open folder after capture", self.settings.auto_open_folder, layout
        )
        self.t_open_folder.toggled.connect(self._on_open_folder_toggled)

        layout.addWidget(Divider())

        # ── STORAGE INFO ──
        layout.addWidget(SectionHeader("💾", "Storage"))

        self.lbl_storage = QLabel("")
        self.lbl_storage.setWordWrap(True)
        self.lbl_storage.setStyleSheet(
            f"color: {theme.BRAND_TEXT_SOFT}; font-size: 10px; font-family: {theme.FONT_MONO};"
        )
        layout.addWidget(self.lbl_storage)
        self._update_storage_info()

        layout.addStretch()
        self.scroll_area.setWidget(content)
        main_layout.addWidget(self.scroll_area)

    def _make_combo(self):
        combo = QComboBox()
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {theme.BRAND_DARK};
                border: 1px solid {theme.BRAND_BORDER};
                border-radius: 6px; padding: 6px 10px;
                color: {theme.BRAND_TEXT}; font-family: {theme.FONT_MONO};
                font-size: 11px; min-width: 0px;
            }}
            QComboBox:focus {{ border: 1px solid {theme.BRAND_CYAN}; }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background-color: {theme.BRAND_CARD};
                border: 1px solid {theme.BRAND_BORDER};
                color: {theme.BRAND_TEXT};
                selection-background-color: rgba(0, 212, 170, 48);
                font-family: {theme.FONT_MONO}; font-size: 11px;
            }}
        """)
        return combo

    def _on_video_dir_changed(self, path):
        self.settings.video_dir = path
        self.settings.save()
        self._update_storage_info()

    def _on_photo_dir_changed(self, path):
        self.settings.photo_dir = path
        self.settings.save()

    def _on_video_format_changed(self, idx):
        self.settings.video_format_idx = idx
        self.settings.save()
        vf = self.settings.video_format
        self.lbl_vid_info.setText(f"Extension: {vf['ext']}  ·  Codec: {vf['fourcc']}")
        self.settingsChanged.emit()

    def _on_photo_format_changed(self, idx):
        self.settings.photo_format_idx = idx
        self.settings.save()
        self.settingsChanged.emit()

    def _on_timestamp_toggled(self, val):
        self.settings.timestamp_names = val
        self.settings.save()

    def _on_open_folder_toggled(self, val):
        self.settings.auto_open_folder = val
        self.settings.save()

    def _update_storage_info(self):
        try:
            st = os.statvfs(self.settings.video_dir)
            free_gb = (st.f_bavail * st.f_frsize) / (1024 ** 3)
            total_gb = (st.f_blocks * st.f_frsize) / (1024 ** 3)
            self.lbl_storage.setText(
                f"Video drive: {free_gb:.1f} GB free of {total_gb:.1f} GB\n"
                f"At 1080p 30fps MP4: ~{free_gb * 4:.0f} min recording capacity"
            )
        except Exception:
            self.lbl_storage.setText("Could not determine disk space")
