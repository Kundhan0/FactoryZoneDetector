"""Room inventory loaded from JSON; empty until a blueprint is uploaded."""
from __future__ import annotations

import json
from pathlib import Path

_output = Path(__file__).with_name("output")
_state = _output / "rooms_state.json"
_legacy = _output / "zones.json"
_source = _state if _state.exists() else _legacy
ROOMS = json.loads(_source.read_text(encoding="utf-8")).get("rooms", {}) if _source.exists() else {}
