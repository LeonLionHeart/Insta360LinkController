#!/usr/bin/env python3
# backend_v4l2.py

import subprocess
import re

class V4L2Backend:
    def __init__(self, device="/dev/video0"):
        self.device = device
        self.current_model = "No Device"

    def get_insta360_cameras(self):
        try:
            result = subprocess.run(["v4l2-ctl", "--list-devices"], capture_output=True, text=True, check=True)
            output = result.stdout
            cameras = {}
            current_name = None
            for line in output.split('\n'):
                line = line.strip()
                if not line: continue
                if not line.startswith('/dev/video'):
                    current_name = line.split(' (')[0]
                elif current_name and ("Insta360" in current_name or "Link" in current_name):
                    if current_name not in cameras:
                        cameras[current_name] = line
            return cameras
        except Exception as e: return {}

    def set_device(self, device, name):
        self.device = device
        self.current_model = name

    def _run_cmd(self, args):
        try:
            cmd = ["v4l2-ctl", "-d", self.device] + args
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except: return None

    def check_connection(self):
        output = self._run_cmd(["--info"])
        return output is not None and "Video Capture" in output

    def set_control(self, control_name, value):
        self._run_cmd(["-c", f"{control_name}={value}"])

    def set_exposure_auto(self, is_auto):
        val = 3 if is_auto else 1
        self._run_cmd(["-c", f"exposure_auto={val}"])
        prio = 1 if is_auto else 0
        self._run_cmd(["-c", f"exposure_auto_priority={prio}"])

    def set_gain_auto(self, is_auto):
        val = 1 if is_auto else 0
        self._run_cmd(["-c", f"gain_automatic={val}"])
        
    def set_hdr(self, enabled):
        val = 1 if enabled else 0
        self._run_cmd(["-c", f"wide_dynamic_range={val}"])
        self._run_cmd(["-c", f"backlight_compensation={val}"])

    def set_format(self, width, height, fps):
        self._run_cmd([f"--set-fmt-video=width={width},height={height},pixelformat=MJPG"])
        self._run_cmd([f"--set-parm={fps}"])

    def get_control(self, control_name):
        output = self._run_cmd(["-C", control_name])
        if output:
            match = re.search(r":\s*(-?\d+)", output)
            if match: return int(match.group(1))
        return None

    def reset_to_defaults(self):
        basic_ctrls = ["brightness", "contrast", "saturation", "sharpness", "hue"]
        for ctrl in basic_ctrls: self.set_control(ctrl, 50)
        self.set_exposure_auto(True)
        self.set_gain_auto(True)
        self.set_control("white_balance_automatic", 1)
        self.set_hdr(False)
        self.set_control("pan_absolute", 0)
        self.set_control("tilt_absolute", 0)
        self.set_control("focus_automatic_continuous", 1)
