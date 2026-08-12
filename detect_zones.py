"""Discover approved room labels from a blueprint using config.py."""
from __future__ import annotations
import argparse
from collections import defaultdict
from pathlib import Path
import re
import shutil
import cv2
import pytesseract
from config import ROOM_KEYWORDS, NON_ROOM_KEYWORDS


def classify_room(text: str) -> str | None:
    """Accept only physical-room labels listed in config.py."""
    value = re.sub(r"\s+", " ", text.lower()).strip()
    if any(item in value for item in NON_ROOM_KEYWORDS) or any(c.isdigit() for c in value):
        return None
    for zone, names in ROOM_KEYWORDS.items():
        # Exact matching is intentional: a dashboard phrase containing the
        # word "server" or "orange" must not become a server room.
        if value in names:
            return zone
    return None


def _tesseract() -> str:
    executable = shutil.which("tesseract")
    for candidate in (Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"), Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe")):
        if not executable and candidate.exists(): executable = str(candidate)
    if not executable:
        raise RuntimeError("Tesseract OCR is required to read room labels. Install it and add it to PATH.")
    return executable


def process_blueprint(image_path: str) -> dict:
    image = cv2.imread(image_path)
    if image is None: raise FileNotFoundError(f"Cannot open blueprint: {image_path}")
    pytesseract.pytesseract.tesseract_cmd = _tesseract()
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config="--psm 11")
    grouped = defaultdict(list)
    for i, raw in enumerate(data["text"]):
        if raw.strip(): grouped[(data["block_num"][i], data["par_num"][i], data["line_num"][i])].append(i)
    lines = []
    for indexes in grouped.values():
        lines.append((" ".join(data["text"][i].strip() for i in indexes), min(data["left"][i] for i in indexes), min(data["top"][i] for i in indexes), max(data["left"][i] + data["width"][i] for i in indexes), max(data["top"][i] + data["height"][i] for i in indexes)))
    candidates = list(lines)
    # Multi-line labels: FURNACE + COMPLEX, FIRST AID + STATION, etc.
    for first in lines:
        for second in lines:
            if first is second or not (first[2] < second[2] <= first[4] + 75): continue
            if abs((first[1] + first[3]) / 2 - (second[1] + second[3]) / 2) < 180:
                candidates.append((f"{first[0]} {second[0]}", min(first[1], second[1]), first[2], max(first[3], second[3]), second[4]))
    accepted = []
    for label, left, top, right, bottom in candidates:
        normalized = re.sub(r"[^A-Z0-9 ]", "", label.upper()).strip()
        zone = classify_room(label)
        if not zone: continue
        pad = max(45, min(image.shape[:2]) // 12)
        x1, y1 = max(0, left-pad), max(0, top-pad)
        x2, y2 = min(image.shape[1], right+pad), min(image.shape[0], bottom+pad)
        accepted.append((normalized, zone, (x1, y1, x2-x1, y2-y1)))
    # Prefer a complete multi-line name over a shorter piece of that same
    # label, for example CHEMICAL PROCESSING over CHEMICAL.
    rooms = {}
    for normalized, zone, rect in sorted(accepted, key=lambda item: len(item[0]), reverse=True):
        if normalized in rooms: continue
        if any(normalized in existing and _overlaps(rect, details["rect"]) for existing, details in rooms.items()):
            continue
        rooms[normalized] = {"rect": rect, "zone": zone, "base_zone": zone, "camera": None, "status": "UNMONITORED"}
    if not rooms: raise RuntimeError("No configured room labels found. Add your room name to ROOM_KEYWORDS in config.py.")
    return rooms


def _overlaps(first: tuple, second: tuple) -> bool:
    """Whether two padded OCR label boxes are from the same room label."""
    ax, ay, aw, ah = first; bx, by, bw, bh = second
    return max(ax, bx) < min(ax + aw, bx + bw) and max(ay, by) < min(ay + ah, by + bh)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("blueprint"); args = parser.parse_args()
    from rooms import ROOMS
    from zone_manager import save_rooms
    ROOMS.clear(); ROOMS.update(process_blueprint(args.blueprint)); save_rooms()
    from map_generator import draw_factory_map
    print(draw_factory_map(args.blueprint)["statistics"])
