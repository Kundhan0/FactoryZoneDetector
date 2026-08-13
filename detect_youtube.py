"""Shared OpenCV fire/smoke detector for one YouTube, RTSP, HTTP, or file source.

Usage:
    python detect_youtube.py
    python detect_youtube.py "https://www.youtube.com/shorts/9qhfEc7oEjw"
"""
from __future__ import annotations

import argparse
import os
import cv2

from fire_smoke_detection import FireSmokeDetector, open_camera

DEFAULT_URL = "https://www.youtube.com/shorts/9qhfEc7oEjw"


def detect_source(source: str, title: str = "Camera", confirm_frames: int = 10,
                  on_alert=None, show: bool | None = None) -> None:
    """Open one camera window and return when its video ends or q is pressed.

    ``on_alert(event)`` is called once with ``FIRE`` or ``SMOKE`` after the
    required number of consecutive positive frames.
    """
    # Render and other Linux servers have no GUI/display. Keep desktop camera
    # windows for local development, but process frames headlessly in deploys.
    if show is None:
        show = not bool(os.getenv("RENDER")) and bool(os.getenv("DISPLAY") or os.name == "nt")
    print(f"[{title}] opening video: {source}", flush=True)
    cap = open_camera(source)
    if not cap.isOpened():
        print(f"[{title}] could not open camera", flush=True)
        return
    detector = FireSmokeDetector()
    fire_frames = smoke_frames = 0
    alerted = False
    window = f"Camera: {title}"
    print(f"[{title}] detection started{' (headless mode)' if not show else '. Press q for next camera.'}", flush=True)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print(f"[{title}] video finished.", flush=True)
                break
            fire, smoke = detector.detect(frame)
            fire_frames = fire_frames + 1 if fire else 0
            smoke_frames = smoke_frames + 1 if smoke else 0
            event = "FIRE" if fire_frames >= confirm_frames else ("SMOKE" if smoke_frames >= confirm_frames else None)
            if event and not alerted:
                alerted = True
                print(f"[{title}] ALERT: {event} DETECTED", flush=True)
                if on_alert:
                    on_alert(event)
            if show:
                label, color = "Monitoring", (0, 255, 0)
                if event == "FIRE": label, color = "FIRE DETECTED", (0, 0, 255)
                elif event == "SMOKE": label, color = "SMOKE DETECTED", (255, 255, 0)
                cv2.putText(frame, label, (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
                cv2.putText(frame, "q = next camera", (20, 75), cv2.FONT_HERSHEY_SIMPLEX, .6, (255, 255, 255), 1)
                cv2.imshow(window, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print(f"[{title}] skipped; opening next camera.", flush=True)
                    break
    finally:
        cap.release()
        if show:
            cv2.destroyWindow(window)


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect fire and smoke in one YouTube video.")
    parser.add_argument("url", nargs="?", default=DEFAULT_URL, help="YouTube, RTSP, HTTP, or video-file source")
    parser.add_argument("--confirm-frames", type=int, default=10, help="Continuous detections required before alert")
    args = parser.parse_args()

    detect_source(args.url, "YouTube Fire & Smoke Detection", args.confirm_frames,
                  lambda event: print(f"ALERT: {event} DETECTED", flush=True))
    print("Detection stopped.", flush=True)


if __name__ == "__main__":
    main()
