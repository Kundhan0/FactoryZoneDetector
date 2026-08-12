"""Frame-by-frame fire/smoke detector usable with a file, RTSP, HTTP, or YouTube stream."""
from __future__ import annotations
import cv2
import numpy as np
from pathlib import Path


class FireSmokeDetector:
    def __init__(self, min_fire_area: int = 2500, min_smoke_area: int = 4000, warmup_frames: int = 90):
        self.min_fire_area, self.min_smoke_area = min_fire_area, min_smoke_area
        self.warmup_frames = warmup_frames
        self.frames_seen = 0
        self.background = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=45, detectShadows=False)

    def detect(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.bitwise_or(cv2.inRange(hsv, (0, 120, 70), (10, 255, 255)), cv2.inRange(hsv, (170, 120, 70), (180, 255, 255)))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        fire = any(cv2.contourArea(c) >= self.min_fire_area for c in cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0])
        # Background subtraction reports nearly the whole frame during its
        # first seconds. Learn the scene first, then require moving *grey*,
        # mid-brightness smoke rather than any bright moving object (clouds,
        # lights, people, or outdoor foliage previously caused false alerts).
        moving = self.background.apply(frame)
        self.frames_seen += 1
        saturation = hsv[:, :, 1]
        brightness = hsv[:, :, 2]
        grey_smoke = cv2.inRange(saturation, 0, 55)
        mid_brightness = cv2.inRange(brightness, 65, 215)
        smoke_mask = cv2.bitwise_and(cv2.bitwise_and(grey_smoke, mid_brightness), moving)
        smoke_mask = cv2.morphologyEx(smoke_mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        maximum_area = frame.shape[0] * frame.shape[1] * 0.15
        smoke = self.frames_seen > self.warmup_frames and any(
            self.min_smoke_area <= cv2.contourArea(c) <= maximum_area
            for c in cv2.findContours(smoke_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
        )
        return fire, smoke


def open_camera(source: str):
    if "youtube.com" in source or "youtu.be" in source:
        import yt_dlp
        # OpenCV on Windows often cannot open a signed googlevideo HTTPS URL.
        # Downloading to a local MP4 makes the same YouTube link usable by the
        # detector and avoids CAP_IMAGES/URL parsing errors.
        cache = Path("output") / "camera_cache"
        cache.mkdir(parents=True, exist_ok=True)
        options = {
            "quiet": True,
            "noplaylist": True,
            "format": "best[ext=mp4]/best",
            "outtmpl": str(cache / "%(id)s.%(ext)s"),
            "merge_output_format": "mp4",
            # Android extraction generally works without browser cookies.
            "extractor_args": {"youtube": {"player_client": ["android"]}},
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(source, download=True)
                source = ydl.prepare_filename(info)
                if not Path(source).exists():
                    source = str(cache / f"{info['id']}.mp4")
            print(f"YouTube video cached locally: {source}", flush=True)
        except Exception as error:
            print(f"Could not download YouTube video: {error}", flush=True)
            return cv2.VideoCapture()
    return cv2.VideoCapture(str(source))
