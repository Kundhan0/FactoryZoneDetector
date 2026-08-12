"""Dedicated desktop process for OpenCV windows.

It is launched by the web control page. Keeping OpenCV in this process (rather
than a FastAPI thread) lets Windows create one visible window per camera.
"""
from __future__ import annotations

import json
import argparse
from pathlib import Path
from monitor import monitor_all
from rooms import ROOMS


parser = argparse.ArgumentParser()
parser.add_argument("--confirm-frames", type=int, default=10)
args = parser.parse_args()

state = Path("output/system_state.json")
if not state.exists():
    raise SystemExit("No blueprint is configured. Upload a blueprint first.")

blueprint = json.loads(state.read_text(encoding="utf-8"))["blueprint"]
camera_names = [name for name, room in ROOMS.items() if room.get("camera")]
print(f"OPENCV RUNNER STARTED: opening {len(camera_names)} camera window(s): {', '.join(camera_names)}", flush=True)
print("Press q in any OpenCV window to stop all cameras.", flush=True)
monitor_all(blueprint, args.confirm_frames)
print("OPENCV RUNNER STOPPED", flush=True)
