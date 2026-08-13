"""Sequential room-camera monitoring using the shared YouTube detector."""
from __future__ import annotations

import argparse

from detect_youtube import detect_source
from map_generator import draw_factory_map
from rooms import ROOMS
from zone_manager import save_rooms, set_camera, set_monitoring, update_zone


def monitor_room(name: str, source: str, blueprint: str, confirm_frames: int = 10,
                 show: bool = True) -> None:
    """Detect one camera; pressing q closes it so monitor_all advances."""
    set_monitoring(name, True)
    save_rooms()
    draw_factory_map(blueprint)

    def on_alert(event: str) -> None:
        update_zone(name, fire=event == "FIRE", smoke=event == "SMOKE")
        save_rooms()
        draw_factory_map(blueprint)
        print(f"[{name}] HIGH ALERT; map updated", flush=True)

    try:
        detect_source(source, title=name, confirm_frames=confirm_frames, on_alert=on_alert)
    finally:
        set_monitoring(name, False)
        save_rooms()
        draw_factory_map(blueprint)
        print(f"[{name}] camera finished", flush=True)


def monitor_all(blueprint: str, confirm_frames: int = 10) -> None:
    """Run all saved cameras one by one; q advances to the next camera."""
    cameras = [(name, room["camera"]) for name, room in ROOMS.items() if room.get("camera")]
    if not cameras:
        print("No configured cameras.", flush=True)
        return
    for index, (name, source) in enumerate(cameras, start=1):
        print(f"[{index}/{len(cameras)}] Opening {name}", flush=True)
        monitor_room(name, source, blueprint, confirm_frames)
    print("All configured cameras finished.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blueprint")
    parser.add_argument("--camera", action="append", default=[], metavar="ROOM=URL")
    parser.add_argument("--confirm-frames", type=int, default=10)
    args = parser.parse_args()
    for assignment in args.camera:
        if "=" not in assignment:
            parser.error("--camera must be ROOM=URL")
        room, source = assignment.split("=", 1)
        set_camera(room.upper(), source)
    save_rooms()
    monitor_all(args.blueprint, args.confirm_frames)


if __name__ == "__main__":
    main()
