#!/usr/bin/env python3
# lut_engine.py

import numpy as np
import cv2


def _clamp(img):
    return np.clip(img, 0, 255).astype(np.uint8)


def lut_natural(frame):
    """No change — identity."""
    return frame.copy()


def lut_warm_sunset(frame):
    """Warm orange push, lifted shadows."""
    f = frame.astype(np.float32)
    b, g, r = cv2.split(f)
    r = r * 1.15 + 10
    g = g * 1.02
    b = b * 0.85
    return _clamp(cv2.merge([b, g, r]))


def lut_cool_blue(frame):
    """Cool blue tint, slightly desaturated."""
    f = frame.astype(np.float32)
    b, g, r = cv2.split(f)
    b = b * 1.15 + 8
    g = g * 1.0
    r = r * 0.88
    return _clamp(cv2.merge([b, g, r]))


def lut_cinematic(frame):
    """Orange & teal — classic cinema look."""
    f = frame.astype(np.float32)
    b, g, r = cv2.split(f)
    # Teal shadows, warm highlights
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    shadow_mask = np.clip(1.0 - luminance / 180.0, 0, 1)
    highlight_mask = np.clip(luminance / 200.0, 0, 1)
    b = b + shadow_mask * 18 - highlight_mask * 8
    g = g + shadow_mask * 6 - highlight_mask * 2
    r = r - shadow_mask * 6 + highlight_mask * 15
    # Slight contrast boost
    mid = 128.0
    contrast = 1.1
    b = (b - mid) * contrast + mid
    g = (g - mid) * contrast + mid
    r = (r - mid) * contrast + mid
    return _clamp(cv2.merge([b, g, r]))


def lut_vintage_film(frame):
    """Faded film — lifted blacks, slight color shift."""
    f = frame.astype(np.float32)
    b, g, r = cv2.split(f)
    # Lift blacks
    lift = 20.0
    b = b * 0.9 + lift
    g = g * 0.92 + lift * 0.8
    r = r * 0.95 + lift * 0.6
    # Slight green tint in midtones
    g = g + 5
    # Reduce contrast
    mid = 128.0
    b = (b - mid) * 0.85 + mid
    g = (g - mid) * 0.85 + mid
    r = (r - mid) * 0.85 + mid
    return _clamp(cv2.merge([b, g, r]))


def lut_bw(frame):
    """Black & white with rich tonal range."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Apply slight S-curve for richer tones
    lut_table = np.array([
        int(255 * (1 / (1 + np.exp(-0.03 * (x - 128)))))
        for x in range(256)
    ], dtype=np.uint8)
    gray = cv2.LUT(gray, lut_table)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def lut_high_contrast(frame):
    """Punchy high contrast, saturated."""
    f = frame.astype(np.float32)
    mid = 128.0
    contrast = 1.35
    f = (f - mid) * contrast + mid
    # Boost saturation
    hsv = cv2.cvtColor(_clamp(f), cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = hsv[:, :, 1] * 1.25
    hsv = _clamp(hsv)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def lut_moody(frame):
    """Dark, desaturated, crushed shadows."""
    f = frame.astype(np.float32)
    # Desaturate
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = hsv[:, :, 1] * 0.6
    hsv[:, :, 2] = hsv[:, :, 2] * 0.8
    f = cv2.cvtColor(_clamp(hsv), cv2.COLOR_HSV2BGR).astype(np.float32)
    # Cool tint
    b, g, r = cv2.split(f)
    b = b * 1.05 + 5
    r = r * 0.95
    # Crush shadows
    result = cv2.merge([b, g, r])
    result = np.where(result < 30, result * 0.5, result)
    return _clamp(result)


def lut_golden_hour(frame):
    """Warm golden glow, soft highlights."""
    f = frame.astype(np.float32)
    b, g, r = cv2.split(f)
    r = r * 1.2 + 15
    g = g * 1.05 + 5
    b = b * 0.8
    # Soften highlights
    result = cv2.merge([b, g, r])
    result = np.where(result > 220, 220 + (result - 220) * 0.3, result)
    return _clamp(result)


def lut_pastel(frame):
    """Soft pastel — lifted, low contrast, gentle saturation."""
    f = frame.astype(np.float32)
    # Reduce contrast
    mid = 128.0
    f = (f - mid) * 0.7 + mid + 20
    # Desaturate slightly
    hsv = cv2.cvtColor(_clamp(f), cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = hsv[:, :, 1] * 0.7
    return cv2.cvtColor(_clamp(hsv), cv2.COLOR_HSV2BGR)


# ── Registry ──

LUTS = [
    {"id": "natural", "name": "Natural", "fn": lut_natural},
    {"id": "warm_sunset", "name": "Warm Sunset", "fn": lut_warm_sunset},
    {"id": "cool_blue", "name": "Cool Blue", "fn": lut_cool_blue},
    {"id": "cinematic", "name": "Cinematic", "fn": lut_cinematic},
    {"id": "vintage", "name": "Vintage Film", "fn": lut_vintage_film},
    {"id": "bw", "name": "B&W", "fn": lut_bw},
    {"id": "high_contrast", "name": "Hi-Contrast", "fn": lut_high_contrast},
    {"id": "moody", "name": "Moody", "fn": lut_moody},
    {"id": "golden_hour", "name": "Golden Hour", "fn": lut_golden_hour},
    {"id": "pastel", "name": "Pastel", "fn": lut_pastel},
]


def apply_lut(frame, lut_id):
    """Apply a LUT by ID to a BGR frame. Returns new frame."""
    for lut in LUTS:
        if lut["id"] == lut_id:
            return lut["fn"](frame)
    return frame


def generate_thumbnail(frame, lut_fn, width=96, height=54):
    """Generate a small thumbnail of a frame with a LUT applied."""
    small = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    result = lut_fn(small)
    return result
