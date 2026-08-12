"""Render the current room state on top of the original blueprint."""
from __future__ import annotations

import json
from pathlib import Path
import cv2
from rooms import ROOMS
from zone_manager import get_statistics

# BGR: confirmed fire/smoke is black, distinct from normal red-risk rooms.
ZONE_COLORS = {"high_alert": (0, 0, 0), "red": (0, 0, 255), "orange": (0, 165, 255), "yellow": (0, 255, 255), "green": (0, 200, 0)}


def draw_factory_map(blueprint_path: str, output_path: str = "output/colored_output.png",
                     data_path: str = "output/zones.json") -> dict:
    image = cv2.imread(blueprint_path)
    if image is None:
        raise FileNotFoundError(f"Cannot open blueprint: {blueprint_path}")
    overlay = image.copy()
    for name, room in ROOMS.items():
        x, y, w, h = room["rect"]
        color = ZONE_COLORS[room["zone"]]
        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
        cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
        camera = "CAMERA" if room.get("camera") else "NO CAMERA"
        label = f"{name}: {room['zone'].upper()} / {camera}"
        cv2.putText(image, label, (x + 4, max(18, y + 20)), cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1, cv2.LINE_AA)
    rendered = cv2.addWeighted(overlay, .35, image, .65, 0)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(output_path, rendered)
    report = {"rooms": ROOMS, "statistics": get_statistics(), "blueprint": str(blueprint_path)}
    Path(data_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
