#!/usr/bin/env python3
# bg_engine.py
#
# Performance-critical compositing for 4K 30fps:
#   - ZERO float32 conversions (the #1 4K killer — 400MB/frame)
#   - uint8 mask + cv2 C++ operations instead of numpy broadcasting
#   - Half-res blur (blur doesn't need full res)
#   - CUDA: full GPU pipeline — upload once, download once
#   - Frame skip: segmentation every 3rd frame

import cv2
import numpy as np
import os
import sys
import urllib.request
import time

HAS_MEDIAPIPE = False
_MP_ERROR = ""
_API_MODE = None

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
    if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'selfie_segmentation'):
        _API_MODE = "solutions"
    elif hasattr(mp, 'tasks'):
        _API_MODE = "tasks"
    print(f"[bg_engine] mediapipe {mp.__version__}, API={_API_MODE}", file=sys.stderr)
except ImportError as e:
    _MP_ERROR = str(e)
    print(f"[bg_engine] mediapipe not available: {e}", file=sys.stderr)

CONFIG_DIR = os.path.expanduser("~/.config/insta360-link")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite"
MODEL_PATH = os.path.join(CONFIG_DIR, "selfie_segmenter.tflite")
_SEG_W = 256
_SEG_H = 256

# ── Detect GPU ──

HAS_CUDA = False
HAS_OPENCL = False

try:
    if cv2.cuda.getCudaEnabledDeviceCount() > 0:
        HAS_CUDA = True
        print(f"[bg_engine] CUDA device found", file=sys.stderr)
except:
    pass

if not HAS_CUDA:
    try:
        t = cv2.UMat(np.zeros((16, 16, 3), dtype=np.uint8))
        cv2.GaussianBlur(t, (3, 3), 0)
        HAS_OPENCL = True
        print(f"[bg_engine] OpenCL available", file=sys.stderr)
    except:
        pass

_ACCEL = "cuda" if HAS_CUDA else ("opencl" if HAS_OPENCL else "cpu")
print(f"[bg_engine] acceleration: {_ACCEL}", file=sys.stderr)


def _download_model():
    if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 10000:
        return True
    os.makedirs(CONFIG_DIR, exist_ok=True)
    print(f"[bg_engine] Downloading model...", file=sys.stderr)
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        return True
    except Exception as e:
        print(f"[bg_engine] Download failed: {e}", file=sys.stderr)
        return False


class _TasksSegmenter:
    def __init__(self): self._seg = None; self._ts = 0
    def init(self):
        if not _download_model(): return False
        try:
            from mediapipe.tasks.python import vision, BaseOptions
            opts = vision.ImageSegmenterOptions(
                base_options=BaseOptions(model_asset_path=MODEL_PATH),
                running_mode=vision.RunningMode.VIDEO,
                output_confidence_masks=True, output_category_mask=False)
            self._seg = vision.ImageSegmenter.create_from_options(opts)
            print(f"[bg_engine] Tasks segmenter OK", file=sys.stderr); return True
        except Exception as e:
            print(f"[bg_engine] Tasks: {e}", file=sys.stderr); return False
    def process(self, rgb):
        if not self._seg: return None
        try:
            self._ts += 33
            r = self._seg.segment_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), self._ts)
            if r and r.confidence_masks and len(r.confidence_masks) > 0:
                return r.confidence_masks[0].numpy_view().copy()
        except: pass
        return None
    def close(self):
        if self._seg:
            try: self._seg.close()
            except: pass


class _SolutionsSegmenter:
    def __init__(self): self._seg = None
    def init(self):
        try:
            self._seg = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=0)
            return True
        except: return False
    def process(self, rgb):
        if not self._seg: return None
        r = self._seg.process(rgb)
        return r.segmentation_mask if r.segmentation_mask is not None else None
    def close(self):
        if self._seg:
            try: self._seg.close()
            except: pass


class VirtualBackgroundEngine:
    def __init__(self):
        self.mode = "none"
        self._bg_image_path = ""
        self._bg_image = None
        self._blur_strength = 21
        self._segmenter = None
        self._available = False
        self._init_error = ""
        self._last_w = 0; self._last_h = 0
        self._log_count = 0
        self._skip_interval = 3
        self._skip_count = 0
        # Mask stored as uint8 0-255 (not float32!)
        self._cached_mask = None     # uint8 HxW
        self._cached_mask_inv = None # uint8 HxW
        self._cached_mask_3ch = None # uint8 HxWx3
        self._cached_inv_3ch = None  # uint8 HxWx3
        self._smoothing = 0.65

        if not HAS_MEDIAPIPE:
            self._init_error = _MP_ERROR; return

        if _API_MODE == "solutions":
            seg = _SolutionsSegmenter()
            if seg.init(): self._segmenter = seg; self._available = True
            else: self._init_error = "Solutions init failed"
        elif _API_MODE == "tasks":
            seg = _TasksSegmenter()
            if seg.init(): self._segmenter = seg; self._available = True
            else: self._init_error = "Tasks init failed"
        else:
            self._init_error = "No MediaPipe API"

        print(f"[bg_engine] ready={self._available} accel={_ACCEL}", file=sys.stderr)

    @staticmethod
    def is_available(): return HAS_MEDIAPIPE

    def get_status(self):
        if not HAS_MEDIAPIPE: return "mediapipe not installed"
        if not self._available: return f"Init failed: {self._init_error}"
        return f"Ready · {_ACCEL.upper()}"

    def set_mode(self, mode, image_path=""):
        print(f"[bg_engine] set_mode({mode!r}) accel={_ACCEL}", file=sys.stderr)
        self.mode = mode
        if mode == "image" and image_path:
            self._bg_image_path = image_path; self._bg_image = None; self._last_w = 0
        elif mode != "image":
            self._bg_image_path = ""; self._bg_image = None
        self._clear_masks()

    def set_blur_strength(self, s):
        s = max(5, min(99, s))
        if s % 2 == 0: s += 1
        self._blur_strength = s

    def _clear_masks(self):
        self._cached_mask = None; self._cached_mask_inv = None
        self._cached_mask_3ch = None; self._cached_inv_3ch = None
        self._skip_count = 0
        if hasattr(self, '_green_bg'): del self._green_bg

    def process_frame(self, frame):
        if self.mode == "none": return frame
        if not self._available or self._segmenter is None: return frame

        h, w = frame.shape[:2]

        # Invalidate cache if resolution changed
        if self._cached_mask is not None and self._cached_mask.shape[:2] != (h, w):
            self._clear_masks()
            self._last_w = 0  # force bg_image resize

        # ── Run segmentation every Nth frame ──
        self._skip_count += 1
        if self._skip_count >= self._skip_interval or self._cached_mask is None:
            self._skip_count = 0
            mask_f = self._run_segmentation(frame, w, h)
            if mask_f is not None:
                self._build_mask_cache(mask_f, w, h)

        if self._cached_mask_3ch is None:
            return frame

        # ── Composite using uint8 math (no float32!) ──
        if HAS_CUDA:
            result = self._composite_cuda(frame, w, h)
            if result is not None: return result

        return self._composite_fast(frame, w, h)

    def _run_segmentation(self, frame, w, h):
        """Run MediaPipe at 256x256, return float32 mask at frame resolution."""
        try:
            small = cv2.resize(frame, (_SEG_W, _SEG_H), interpolation=cv2.INTER_LINEAR)
            small_rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            mask_raw = self._segmenter.process(small_rgb)
            if mask_raw is None: return None
            if len(mask_raw.shape) > 2: mask_raw = np.squeeze(mask_raw)

            # Upscale + feather
            mask = cv2.resize(mask_raw, (w, h), interpolation=cv2.INTER_LINEAR)
            mask = cv2.GaussianBlur(mask, (5, 5), 2)
            return np.clip(mask, 0.0, 1.0)
        except Exception as e:
            self._log_count += 1
            if self._log_count % 300 == 1:
                print(f"[bg_engine] seg error: {e}", file=sys.stderr)
            return None

    def _build_mask_cache(self, mask_f, w, h):
        """Convert float mask to uint8 caches. Temporal smoothing in float, store as uint8."""
        # Temporal smoothing (in float, only done when new mask arrives)
        if self._cached_mask is not None and self._cached_mask.shape == (h, w):
            old_f = self._cached_mask.astype(np.float32) / 255.0
            mask_f = self._smoothing * old_f + (1.0 - self._smoothing) * mask_f

        # Convert to uint8 once — reused for 2-3 frames
        mask_u8 = (mask_f * 255).astype(np.uint8)
        inv_u8 = 255 - mask_u8

        self._cached_mask = mask_u8
        self._cached_mask_inv = inv_u8
        self._cached_mask_3ch = cv2.merge([mask_u8, mask_u8, mask_u8])
        self._cached_inv_3ch = cv2.merge([inv_u8, inv_u8, inv_u8])

        self._log_count += 1
        if self._log_count == 1:
            print(f"[bg_engine] First mask cached {w}x{h} mode={self.mode}", file=sys.stderr)

    def _composite_fast(self, frame, w, h):
        """
        Fast uint8 compositing using cv2.multiply + cv2.add.
        No float32 arrays! cv2.multiply with scale=1/255 does the division in C++.
        At 4K this avoids ~400MB of float allocations per frame.
        """
        mask_3ch = self._cached_mask_3ch
        inv_3ch = self._cached_inv_3ch

        bg = self._get_background(frame, w, h)
        if bg is None: return frame

        # fg = frame * (mask / 255)  — done in C++ with scale parameter
        fg = cv2.multiply(frame, mask_3ch, scale=1.0/255.0, dtype=cv2.CV_8U)
        bg_part = cv2.multiply(bg, inv_3ch, scale=1.0/255.0, dtype=cv2.CV_8U)
        return cv2.add(fg, bg_part)

    def _composite_cuda(self, frame, w, h):
        """Full CUDA pipeline: upload → blur/bg → multiply → add → download."""
        try:
            g_frame = cv2.cuda_GpuMat()
            g_frame.upload(frame)

            g_mask = cv2.cuda_GpuMat()
            g_mask.upload(self._cached_mask_3ch)
            g_inv = cv2.cuda_GpuMat()
            g_inv.upload(self._cached_inv_3ch)

            # Get background on GPU
            if self.mode == "blur":
                # Blur on GPU — the big win for CUDA
                filt = cv2.cuda.createGaussianFilter(
                    cv2.CV_8UC3, cv2.CV_8UC3,
                    (self._blur_strength, self._blur_strength), 0)
                g_bg = filt.apply(g_frame)
            elif self.mode == "green":
                green = np.full((h, w, 3), (0, 255, 0), dtype=np.uint8)
                g_bg = cv2.cuda_GpuMat()
                g_bg.upload(green)
            elif self.mode == "image":
                bg_img = self._get_bg_image(w, h)
                if bg_img is None: return None
                g_bg = cv2.cuda_GpuMat()
                g_bg.upload(bg_img)
            else:
                return None

            # Composite on GPU using multiply + add
            g_fg = cv2.cuda.multiply(g_frame, g_mask, scale=1.0/255.0)
            g_bg_part = cv2.cuda.multiply(g_bg, g_inv, scale=1.0/255.0)
            g_result = cv2.cuda.add(g_fg, g_bg_part)

            return g_result.download()
        except Exception as e:
            self._log_count += 1
            if self._log_count % 300 == 1:
                print(f"[bg_engine] CUDA composite fallback: {e}", file=sys.stderr)
            return None

    def _get_background(self, frame, w, h):
        """Get the background frame for compositing."""
        if self.mode == "blur":
            # Blur at half resolution for speed, upscale back
            half_w, half_h = w // 2, h // 2
            small = cv2.resize(frame, (half_w, half_h), interpolation=cv2.INTER_LINEAR)
            blurred_small = cv2.GaussianBlur(small, (self._blur_strength, self._blur_strength), 0)
            return cv2.resize(blurred_small, (w, h), interpolation=cv2.INTER_LINEAR)
        elif self.mode == "green":
            # Allocate once, cache
            if not hasattr(self, '_green_bg') or self._green_bg.shape[:2] != (h, w):
                self._green_bg = np.full((h, w, 3), (0, 255, 0), dtype=np.uint8)
            return self._green_bg
        elif self.mode == "image":
            return self._get_bg_image(w, h)
        return None

    def _get_bg_image(self, w, h):
        if self._bg_image is not None and self._last_w == w and self._last_h == h:
            return self._bg_image
        if not self._bg_image_path or not os.path.exists(self._bg_image_path): return None
        try:
            img = cv2.imread(self._bg_image_path)
            if img is None: return None
            self._bg_image = cv2.resize(img, (w, h), interpolation=cv2.INTER_LINEAR)
            self._last_w = w; self._last_h = h; return self._bg_image
        except: return None

    def release(self):
        print(f"[bg_engine] release()", file=sys.stderr)
        if self._segmenter: self._segmenter.close(); self._segmenter = None
        self._clear_masks(); self._bg_image = None
