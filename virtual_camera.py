#!/usr/bin/env python3
# virtual_camera.py

import subprocess
import os
import json
import shutil
import signal
import glob
import threading

CONFIG_DIR = os.path.expanduser("~/.config/insta360-link")
PROFILES_FILE = os.path.join(CONFIG_DIR, "vcam_profiles.json")


class VCamProfile:
    def __init__(self, name="Default", is_default=False, auto_start=False):
        self.name = name
        self.is_default = is_default
        self.auto_start = auto_start

    def to_dict(self):
        return {"name": self.name, "is_default": self.is_default, "auto_start": self.auto_start}

    @staticmethod
    def from_dict(d):
        return VCamProfile(
            name=d.get("name", "Default"),
            is_default=d.get("is_default", False),
            auto_start=d.get("auto_start", False),
        )


class ProfileManager:
    def __init__(self):
        self.profiles = []
        os.makedirs(CONFIG_DIR, exist_ok=True)
        self._load()
        if not self.profiles:
            self.profiles.append(VCamProfile("Default", is_default=True))
            self._save()

    def _load(self):
        try:
            with open(PROFILES_FILE, "r") as f:
                self.profiles = [VCamProfile.from_dict(d) for d in json.load(f)]
        except Exception:
            self.profiles = []

    def _save(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(PROFILES_FILE, "w") as f:
                json.dump([p.to_dict() for p in self.profiles], f, indent=2)
        except Exception:
            pass

    def get_default(self):
        for p in self.profiles:
            if p.is_default:
                return p
        return self.profiles[0] if self.profiles else None

    def set_default(self, name):
        for p in self.profiles:
            p.is_default = (p.name == name)
        self._save()

    def add_profile(self, name):
        for p in self.profiles:
            if p.name == name:
                return p
        profile = VCamProfile(name=name, is_default=len(self.profiles) == 0)
        self.profiles.append(profile)
        self._save()
        return profile

    def remove_profile(self, name):
        self.profiles = [p for p in self.profiles if p.name != name]
        if self.profiles and not any(p.is_default for p in self.profiles):
            self.profiles[0].is_default = True
        self._save()

    def get_names(self):
        return [p.name for p in self.profiles]

    def save(self):
        self._save()


class VirtualCamera:
    def __init__(self):
        self.is_active = False
        self.device_path = None
        self.device_number = None
        self.profile_name = "Default"
        self.card_label = ""
        self._ffmpeg_proc = None
        self._width = 1920
        self._height = 1080
        self._fps = 30
        self._lock = threading.Lock()
        self._error = None
        self.profile_manager = ProfileManager()

    @staticmethod
    def is_module_installed():
        try:
            return subprocess.run(
                ["modinfo", "v4l2loopback"], capture_output=True, timeout=5
            ).returncode == 0
        except Exception:
            return False

    @staticmethod
    def is_module_loaded():
        try:
            with open("/proc/modules") as f:
                return any(line.startswith("v4l2loopback ") for line in f)
        except Exception:
            return False

    @staticmethod
    def _find_free_video_number():
        existing = set()
        for path in glob.glob("/dev/video*"):
            try:
                existing.add(int(path.replace("/dev/video", "")))
            except ValueError:
                pass
        for n in range(10, 100):
            if n not in existing:
                return n
        return 42

    def get_error(self):
        return self._error

    def _load_module(self, video_nr, card_label):
        if self.is_module_loaded():
            subprocess.run(["modprobe", "-r", "v4l2loopback"], capture_output=True, timeout=5)
        try:
            result = subprocess.run([
                "modprobe", "v4l2loopback", "devices=1",
                f"video_nr={video_nr}", f"card_label={card_label}", "exclusive_caps=1",
            ], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                self._error = f"modprobe failed: {result.stderr.strip()}"
                return False
            return True
        except Exception as e:
            self._error = f"modprobe error: {e}"
            return False

    def _unload_module(self):
        try:
            subprocess.run(["modprobe", "-r", "v4l2loopback"], capture_output=True, timeout=5)
        except Exception:
            pass

    def start(self, profile_name, width=1920, height=1080, fps=30):
        if self.is_active:
            self.stop()
        self._error = None
        self.profile_name = profile_name
        self.card_label = f"Insta360 Link Virtual Camera - {profile_name}"
        self._width = width
        self._height = height
        self._fps = fps

        if not self.is_module_installed():
            self._error = "v4l2loopback kernel module not installed"
            return False
        self.device_number = self._find_free_video_number()
        self.device_path = f"/dev/video{self.device_number}"
        if not self._load_module(self.device_number, self.card_label):
            return False
        if not os.path.exists(self.device_path):
            self._error = f"{self.device_path} not created after modprobe"
            return False

        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            self._error = "ffmpeg not found in PATH"
            return False
        try:
            self._ffmpeg_proc = subprocess.Popen(
                [ffmpeg_path, "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
                 "-pix_fmt", "bgr24", "-s", f"{width}x{height}", "-r", str(fps),
                 "-i", "pipe:0", "-f", "v4l2", "-pix_fmt", "yuyv422", self.device_path],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            self._error = f"Failed to start ffmpeg: {e}"
            return False

        self.is_active = True
        return True

    def stop(self):
        self.is_active = False
        if self._ffmpeg_proc is not None:
            try:
                self._ffmpeg_proc.stdin.close()
            except Exception:
                pass
            try:
                self._ffmpeg_proc.send_signal(signal.SIGTERM)
                self._ffmpeg_proc.wait(timeout=3)
            except Exception:
                try:
                    self._ffmpeg_proc.kill()
                except Exception:
                    pass
            self._ffmpeg_proc = None
        self._unload_module()
        self.device_path = None
        self.device_number = None

    def feed_frame(self, frame):
        if not self.is_active or self._ffmpeg_proc is None:
            return
        with self._lock:
            try:
                h, w = frame.shape[:2]
                if w != self._width or h != self._height:
                    import cv2
                    frame = cv2.resize(frame, (self._width, self._height))
                self._ffmpeg_proc.stdin.write(frame.tobytes())
            except (BrokenPipeError, OSError):
                self.is_active = False
                self._error = "ffmpeg pipe broken — virtual camera stopped"
            except Exception:
                pass
