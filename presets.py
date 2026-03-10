#!/usr/bin/env python3
# presets.py

import os
import json

CONFIG_DIR = os.path.expanduser("~/.config/insta360-link")
PRESETS_FILE = os.path.join(CONFIG_DIR, "scene_presets.json")

DEFAULT_STATE = {
    "res_index": 1,
    "fps": 30,
    "zoom": 100,
    "brightness": 50,
    "contrast": 50,
    "saturation": 50,
    "sharpness": 50,
    "hue": 0,
    "lut_id": "natural",
    "mirror_h": False,
    "flip_v": False,
    "auto_focus": True,
    "focus": 50,
    "auto_wb": True,
    "wb_temp": 6400,
    "bg_mode_idx": 0,
    "bg_image_path": "",
    "bg_blur": 21,
}


class ScenePreset:
    def __init__(self, name="Default", state=None, is_active=False):
        self.name = name
        self.state = dict(DEFAULT_STATE) if state is None else dict(state)
        self.is_active = is_active

    def to_dict(self):
        return {"name": self.name, "state": self.state, "is_active": self.is_active}

    @staticmethod
    def from_dict(d):
        return ScenePreset(
            name=d.get("name", "Default"),
            state=d.get("state", dict(DEFAULT_STATE)),
            is_active=d.get("is_active", False),
        )


class PresetManager:
    def __init__(self):
        self.presets = []
        self.last_active = "Default"
        self._load()
        if not self.presets:
            self.presets = [
                ScenePreset("Default", dict(DEFAULT_STATE), is_active=True),
                ScenePreset("Streaming", {**DEFAULT_STATE, "brightness": 55, "saturation": 55, "zoom": 120}),
                ScenePreset("Whiteboard", {**DEFAULT_STATE, "brightness": 60, "contrast": 60, "sharpness": 65}),
            ]
            self._save()

    def _load(self):
        try:
            with open(PRESETS_FILE, "r") as f:
                data = json.load(f)
            self.presets = [ScenePreset.from_dict(d) for d in data.get("presets", [])]
            self.last_active = data.get("last_active", "Default")
        except Exception:
            self.presets = []

    def _save(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(PRESETS_FILE, "w") as f:
                json.dump({
                    "presets": [p.to_dict() for p in self.presets],
                    "last_active": self.last_active,
                }, f, indent=2)
        except Exception:
            pass

    def get_names(self):
        return [p.name for p in self.presets]

    def get_preset(self, name):
        for p in self.presets:
            if p.name == name:
                return p
        return None

    def get_active(self):
        p = self.get_preset(self.last_active)
        return p if p else (self.presets[0] if self.presets else None)

    def save_preset(self, name, state):
        """Save or update a preset with the given state."""
        existing = self.get_preset(name)
        if existing:
            existing.state = dict(state)
        else:
            self.presets.append(ScenePreset(name, dict(state)))
        self.last_active = name
        self._save()

    def set_active(self, name):
        self.last_active = name
        self._save()

    def add_preset(self, name, state=None):
        if self.get_preset(name):
            return
        self.presets.append(ScenePreset(name, dict(state or DEFAULT_STATE)))
        self._save()

    def remove_preset(self, name):
        if len(self.presets) <= 1:
            return
        self.presets = [p for p in self.presets if p.name != name]
        if self.last_active == name and self.presets:
            self.last_active = self.presets[0].name
        self._save()

    def capture_state(self, **kwargs):
        """Build a state dict from current UI values."""
        state = dict(DEFAULT_STATE)
        state.update(kwargs)
        return state
