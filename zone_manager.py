"""Room state persistence and zone reporting."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from rooms import ROOMS


def _state_file() -> Path:
    return Path(__file__).with_name("output") / "rooms_state.json"


def save_rooms() -> None:
    """Persist state without modifying Python files (prevents API reloads)."""
    target = _state_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({"rooms": ROOMS}, indent=2), encoding="utf-8")
    temporary.replace(target)


def set_camera(room_name: str, source: str | None) -> None:
    if room_name not in ROOMS:
        raise KeyError(f"Unknown room {room_name!r}. Available: {', '.join(ROOMS)}")
    ROOMS[room_name]["camera"] = source
    ROOMS[room_name]["status"] = "NORMAL" if source else "UNMONITORED"


def update_zone(room_name: str, fire: bool = False, smoke: bool = False) -> bool:
    """Mark a camera-equipped room high_alert after a confirmed event.

    Returns True only when the persisted state changed.
    """
    room = ROOMS[room_name]
    if not room.get("camera"):
        return False
    if fire or smoke:
        changed = room.get("zone") != "high_alert" or room.get("status") != "ALERT"
        # Red is a normal high-risk classification.  A confirmed camera event
        # is more serious and must remain distinguishable in map/API data.
        room["zone"] = "high_alert"
        room["status"] = "ALERT"
        room["alert"] = "FIRE" if fire else "SMOKE"
        room["alerted_at"] = datetime.now(timezone.utc).isoformat()
        return changed
    return False


def set_monitoring(room_name: str, monitoring: bool) -> None:
    """Expose whether a configured room camera is currently being scanned."""
    room = ROOMS[room_name]
    if room.get("status") != "ALERT":
        room["status"] = "MONITORING" if monitoring else ("NORMAL" if room.get("camera") else "UNMONITORED")


def clear_alerts() -> None:
    """Restore false/test alerts to their original blueprint classification."""
    for room in ROOMS.values():
        if room.get("status") == "ALERT":
            room["zone"] = room.get("base_zone", "green")
            room["status"] = "NORMAL" if room.get("camera") else "UNMONITORED"
            room.pop("alert", None)
            room.pop("alerted_at", None)


def get_statistics() -> dict:
    stats = {"high_alert": 0, "red": 0, "orange": 0, "yellow": 0, "green": 0,
             "alert_rooms": 0, "monitored_rooms": 0, "unmonitored_rooms": 0}
    for room in ROOMS.values():
        stats[room["zone"]] += 1
        if room.get("camera"):
            stats["monitored_rooms"] += 1
        else:
            stats["unmonitored_rooms"] += 1
        if room.get("status") == "ALERT":
            stats["alert_rooms"] += 1
    return stats
