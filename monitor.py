"""End-to-end runner: build map once, then inspect every configured camera."""
from __future__ import annotations
import argparse
from pathlib import Path
import cv2
from fire_smoke_detection import FireSmokeDetector, open_camera
from map_generator import draw_factory_map
from rooms import ROOMS 
from zone_manager import save_rooms, set_camera, update_zone


def monitor_room(name: str, source: str, blueprint: str, confirm_frames: int, show: bool = False) -> None:
    cap = open_camera(source)
    if not cap.isOpened():
        print(f"[{name}] could not open camera: {source}"); return
    detector, fire_count, smoke_count, alerted = FireSmokeDetector(), 0, 0, False
    while True:
        ok, frame = cap.read()
        if not ok: break  # a supplied video ends here; a live URL can be restarted externally
        fire, smoke = detector.detect(frame)
        fire_count = fire_count + 1 if fire else 0
        smoke_count = smoke_count + 1 if smoke else 0
        if not alerted and (fire_count >= confirm_frames or smoke_count >= confirm_frames):
            alerted = True
            update_zone(name, fire=fire_count >= confirm_frames, smoke=smoke_count >= confirm_frames)
            save_rooms(); draw_factory_map(blueprint)
            print(f"[{name}] ALERT: {'FIRE' if fire_count >= confirm_frames else 'SMOKE'}; map updated")
        if show:
            preview = frame.copy()
            cv2.putText(preview, f"{name} - press q for next camera", (20, 35),
                        cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 255, 0), 2)
            cv2.imshow(f"Camera: {name}", preview)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    cap.release()
    if show:
        cv2.destroyWindow(f"Camera: {name}")
    print(f"[{name}] camera finished")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprint", help="Original blueprint image")
    parser.add_argument("--camera", action="append", default=[], metavar="ROOM=URL",
                        help="Assign a video/live-feed to a discovered room; repeat for every camera")
    parser.add_argument("--confirm-frames", type=int, default=10)
    parser.add_argument("--show", action="store_true", help="Show each camera while it is scanned; press q for the next camera")
    args = parser.parse_args()
    for assignment in args.camera:
        if "=" not in assignment: parser.error("--camera must be ROOM=URL")
        room, source = assignment.split("=", 1); set_camera(room.upper(), source)
    save_rooms(); draw_factory_map(args.blueprint)
    cameras = [(name, data["camera"]) for name, data in ROOMS.items() if data.get("camera")]
    if not cameras: print("No cameras assigned. Add --camera ROOM=URL."); return
    for name, source in cameras:
        monitor_room(name, source, args.blueprint, args.confirm_frames, args.show)


if __name__ == "__main__":
    main()
