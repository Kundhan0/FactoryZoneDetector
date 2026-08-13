"""Website API for blueprint zoning and room-camera monitoring.

Start with: uvicorn api:app --reload
Open http://127.0.0.1:8000/docs to test the API interactively.
"""
from __future__ import annotations

import json
import threading
import html
import time
import subprocess
import sys
import re
import os
from urllib.parse import urlparse
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import URLError
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

from detect_zones import process_blueprint
from map_generator import draw_factory_map
from rooms import ROOMS
from zone_manager import clear_alerts, save_rooms, set_camera, update_zone

OUTPUT = Path("output")
STATE_FILE = OUTPUT / "system_state.json"
running_rooms: set[str] = set()
run_lock = threading.Lock()
camera_process: subprocess.Popen | None = None

app = FastAPI(title="Factory Zone Detector API", version="1.0.0")

# Enable CORS for website integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",")],
    # The detector uses no browser cookies. Keeping this false also permits a
    # local development wildcard while production uses CORS_ORIGINS.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Room data belongs to an uploaded blueprint.  Do not expose stale rooms when
# this API has no uploaded-blueprint state.
if not STATE_FILE.exists():
    ROOMS.clear()


class CameraInput(BaseModel):
    room_name: str
    source: str  # Supports file paths, RTSP/HTTP links, and YouTube links.


class MonitorInput(BaseModel):
    confirm_frames: int = 10


def blueprint_path() -> str:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))["blueprint"]
    raise HTTPException(400, "Upload a blueprint first.")


def redraw() -> dict:
    report = draw_factory_map(blueprint_path())
    report["map_updated_at"] = (OUTPUT / "colored_output.png").stat().st_mtime
    return report


@app.get("/health")
def health():
    return {"ok": True, "monitor_running": bool(camera_process and camera_process.poll() is None), "running_rooms": sorted(running_rooms)}


@app.get("/", response_class=HTMLResponse)
def control_page():
    fields = "".join(
        f'<label>{html.escape(name)}<input name="camera_{name}" value="{html.escape(room.get("camera") or "")}" placeholder="video file, YouTube, RTSP, or HTTP link"></label>'
        for name, room in ROOMS.items()
    ) or "<p>Upload a labelled blueprint first.</p>"
    map_html = (f'<h2>Current coloured map</h2><img id="map" src="/map?t={time.time()}" '
                'style="width:100%;border:1px solid #999"><p id="map-note">Map refreshes every 3 seconds while cameras run.</p>') \
               if STATE_FILE.exists() and (OUTPUT / "colored_output.png").exists() else ""
    camera_cards = "".join(_camera_card(name, room.get("camera")) for name, room in ROOMS.items() if room.get("camera"))
    preview_html = f"<h2>Live camera previews</h2><div class=\"cameras\">{camera_cards}</div>" if camera_cards else ""
    return f'''<!doctype html><title>Factory Fire Monitor</title><style>body{{font-family:Arial;max-width:960px;margin:30px auto}}label,input,button{{display:block;width:100%;box-sizing:border-box;margin:9px 0}}label{{font-weight:bold}}input{{padding:9px}}button{{padding:10px;background:#b91c1c;color:white;border:0;border-radius:4px;font-weight:bold}}.cameras{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}.camera{{border:1px solid #999;padding:8px}}.camera h3{{margin:0 0 7px}}iframe,video{{width:100%;height:220px;border:0}}</style>
    <h1>Factory Fire Monitor</h1><p>1. Upload blueprint. 2. Paste one link for each room. 3. Start all cameras.</p>
    <form action="/page/blueprint" method="post" enctype="multipart/form-data"><input type="file" name="file" accept=".png,.jpg,.jpeg" required><button>1. Upload Blueprint</button></form>
    {map_html}{preview_html}<h2>Camera links</h2><form action="/page/cameras" method="post">{fields}<button>2. Save Cameras and Start Detection</button></form>
    <form action="/page/clear-alerts" method="post"><button type="submit">Clear Alerts (restore blueprint zones)</button></form><form action="/page/reset" method="post"><button type="submit">Clear Blueprint and Room Data</button></form><p><a href="/map?t=1">Open current colored map</a> · <a href="/zones">Zone data (JSON)</a></p>
    <script>setInterval(() => {{ const map = document.getElementById('map'); if (map) map.src = '/map?t=' + Date.now(); }}, 3000);</script>'''


def _camera_card(name: str, source: str) -> str:
    """Return a browser-safe preview for sources browsers can play directly."""
    escaped_name, escaped_source = html.escape(name), html.escape(source, quote=True)
    video_id = re.search(r"(?:youtu\.be/|youtube\.com/(?:shorts/|watch\?v=))([A-Za-z0-9_-]{11})", source)
    if video_id:
        embed = f'<iframe src="https://www.youtube.com/embed/{video_id.group(1)}" title="{escaped_name}" allowfullscreen></iframe>'
    elif source.lower().endswith((".mp4", ".webm", ".ogg")) or source.startswith(("http://", "https://")):
        embed = f'<video controls muted autoplay src="{escaped_source}">Browser cannot play this video.</video>'
    else:
        embed = '<p>Preview unavailable for RTSP. Detection still runs in the desktop detector.</p>'
    return f'<section class="camera"><h3>{escaped_name}</h3>{embed}</section>'


@app.post("/page/blueprint")
async def page_blueprint(file: UploadFile = File(...)):
    await upload_blueprint(file)
    return RedirectResponse("/", status_code=303)


@app.post("/page/reset")
def page_reset():
    """Explicitly clear the current blueprint session and all room data."""
    ROOMS.clear()
    save_rooms()
    for path in (STATE_FILE, OUTPUT / "rooms_state.json", OUTPUT / "zones.json", OUTPUT / "colored_output.png"):
        if path.exists():
            path.unlink()
    print("BLUEPRINT CLEARED: room data is now empty", flush=True)
    return RedirectResponse("/", status_code=303)


@app.post("/page/clear-alerts")
def page_clear_alerts():
    clear_alerts(); save_rooms(); redraw()
    print("ALERTS CLEARED: restored all rooms to blueprint zones", flush=True)
    return RedirectResponse("/", status_code=303)


@app.post("/alerts/clear")
def clear_all_alerts():
    """API version of the Clear Alerts control-page button."""
    clear_alerts(); save_rooms()
    return redraw()


@app.post("/page/cameras")
async def page_cameras(request: Request):
    form = await request.form()
    saved = []
    for name in ROOMS:
        source = str(form.get(f"camera_{name}", "")).strip()
        set_camera(name, source or None)
        if source:
            saved.append(name)
    save_rooms(); redraw()
    print(f"CAMERAS UPDATED: {len(saved)} saved -> {', '.join(saved) if saved else 'none'}", flush=True)
    start_monitoring(MonitorInput())
    return RedirectResponse("/", status_code=303)


@app.post("/blueprint")
async def upload_blueprint(file: UploadFile = File(...)):
    """Upload a labelled .png/.jpg blueprint and initialise all detected rooms."""
    suffix = Path(file.filename or "blueprint.png").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg"}:
        raise HTTPException(400, "Blueprint must be a PNG or JPEG image.")
    target = Path("input") / f"uploaded_blueprint{suffix}"
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(await file.read())
    try:
        detected = process_blueprint(str(target))
    except RuntimeError as error:
        raise HTTPException(500, str(error)) from error
    ROOMS.clear(); ROOMS.update(detected); save_rooms()
    OUTPUT.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps({"blueprint": str(target)}), encoding="utf-8")
    return redraw()


@app.get("/zones")
def zones():
    """Current zone, alert, rectangle and camera information for every room."""
    if not STATE_FILE.exists():
        return {"rooms": {}, "statistics": {"high_alert": 0, "red": 0, "orange": 0, "yellow": 0, "green": 0,
                                               "alert_rooms": 0, "monitored_rooms": 0, "unmonitored_rooms": 0},
                "blueprint": None}
    try:
        return redraw()
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error


class AlertTestInput(BaseModel):
    room_name: str
    event: str = "FIRE"


@app.post("/alerts/test")
def test_alert(alert: AlertTestInput):
    """Test the website/map update path without needing a real fire video."""
    room = alert.room_name.upper()
    if room not in ROOMS:
        raise HTTPException(404, f"Unknown room {room!r}")
    # A test alert works even before a camera link is added, so the blueprint
    # and web integration can be verified independently from camera hardware.
    temporary_camera = not ROOMS[room].get("camera")
    if temporary_camera:
        ROOMS[room]["camera"] = "TEST ALERT (no physical camera)"
    event = alert.event.upper()
    if event not in {"FIRE", "SMOKE"}:
        raise HTTPException(400, "event must be FIRE or SMOKE")
    update_zone(room, fire=event == "FIRE", smoke=event == "SMOKE")
    if temporary_camera:
        ROOMS[room]["camera"] = None
    save_rooms()
    return redraw()


@app.post("/cameras")
def add_camera(camera: CameraInput):
    """Set or replace the camera source for a room discovered from the blueprint."""
    room = camera.room_name.upper()
    try:
        set_camera(room, camera.source)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error
    save_rooms()
    redraw()
    print(f"CAMERA UPDATED: {room} -> {camera.source}", flush=True)
    return {"room_name": room, "source": camera.source, "message": "Camera saved"}


@app.delete("/cameras/{room_name}")
def remove_camera(room_name: str):
    room = room_name.upper()
    try:
        set_camera(room, None)
    except KeyError as error:
        raise HTTPException(404, str(error)) from error
    save_rooms(); redraw()
    return {"room_name": room, "message": "Camera removed"}


@app.post("/monitor/start")
def start_monitoring(request: MonitorInput):
    """Open and monitor every saved camera at the same time."""
    global camera_process
    cameras = [name for name, room in ROOMS.items() if room.get("camera")]
    if not cameras:
        raise HTTPException(400, "Add at least one camera link first.")
    with run_lock:
        if camera_process and camera_process.poll() is None:
            return {"started": [], "already_running": sorted(running_rooms)}
        running_rooms.update(cameras)
        # A separate process is necessary for reliable OpenCV windows on Windows.
        camera_process = subprocess.Popen(
            [sys.executable, "camera_runner.py", "--confirm-frames", str(request.confirm_frames)],
            cwd=Path(__file__).parent,
        )
    return {
        "started": cameras,
        "message": "One OpenCV window opens for every saved camera. Press q in any window to stop all cameras.",
    }


@app.get("/monitor/status")
def monitor_status():
    """Poll this endpoint from the website while monitoring is active."""
    active = bool(camera_process and camera_process.poll() is None)
    if not active:
        running_rooms.clear()
    return {"monitor_running": active, "running_rooms": sorted(running_rooms), "rooms": ROOMS}


@app.get("/map")
def current_map():
    map_file = OUTPUT / "colored_output.png"
    if not STATE_FILE.exists() or not map_file.exists():
        raise HTTPException(404, "No map yet. Upload a blueprint first.")
    # no-store avoids browsers showing an old map after an alert redraw.
    return FileResponse(map_file, media_type="image/png", headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"})


# ============================================================================
# New API Endpoints for Website Integration
# ============================================================================

class CameraData(BaseModel):
    camera_name: str
    location: str = ""
    cloud_url: str = ""


class BlueprintUploadResponse(BaseModel):
    success: bool
    rooms: dict = {}
    statistics: dict = {}
    message: str = ""


class BlueprintUrlInput(BaseModel):
    url: str


def process_blueprint_target(target: Path) -> dict:
    """Populate shared room state and render a new map for a local blueprint."""
    detected = process_blueprint(str(target))
    ROOMS.clear()
    ROOMS.update(detected)
    save_rooms()
    OUTPUT.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps({"blueprint": str(target)}), encoding="utf-8")
    result = redraw()
    return {
        "success": True,
        "rooms": result.get("rooms", {}),
        "statistics": result.get("statistics", {}),
        "message": f"Blueprint processed successfully. Detected {len(detected)} rooms.",
    }


@app.post("/api/blueprint")
async def api_upload_blueprint(file: UploadFile = File(...)):
    """Upload blueprint for website integration and return detected rooms."""
    try:
        suffix = Path(file.filename or "blueprint.png").suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg"}:
            raise HTTPException(400, "Blueprint must be a PNG or JPEG image.")
        
        target = Path("input") / f"uploaded_blueprint{suffix}"
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(await file.read())
        
        return process_blueprint_target(target)
    except RuntimeError as error:
        raise HTTPException(500, f"Blueprint processing failed: {str(error)}")
    except Exception as error:
        raise HTTPException(500, f"Unexpected error: {str(error)}")


@app.post("/api/blueprint-url")
def api_upload_blueprint_url(payload: BlueprintUrlInput):
    """Download a public image URL, process it, and return rooms plus map data."""
    parsed = urlparse(payload.url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(400, "Blueprint URL must be a public http:// or https:// image URL.")
    try:
        request = UrlRequest(payload.url, headers={"User-Agent": "Agni-Hazemap/1.0"})
        with urlopen(request, timeout=20) as response:
            content_type = response.headers.get_content_type()
            if content_type not in {"image/png", "image/jpeg"}:
                raise HTTPException(400, "Blueprint URL must return a PNG or JPEG image, not a web page.")
            image = response.read(15 * 1024 * 1024 + 1)
        if len(image) > 15 * 1024 * 1024:
            raise HTTPException(400, "Blueprint image must be 15 MB or smaller.")
        suffix = ".png" if content_type == "image/png" else ".jpg"
        target = Path("input") / f"url_blueprint{suffix}"
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(image)
        return process_blueprint_target(target)
    except HTTPException:
        raise
    except (URLError, TimeoutError) as error:
        raise HTTPException(400, f"Could not download blueprint URL: {error}") from error
    except RuntimeError as error:
        raise HTTPException(500, f"Blueprint processing failed: {error}") from error
    except Exception as error:
        raise HTTPException(500, f"Unexpected error: {error}") from error


@app.get("/api/rooms")
def api_get_rooms():
    """Get formatted rooms data for website display."""
    if not ROOMS:
        return {
            "success": False,
            "rooms": {},
            "statistics": {
                "total": 0,
                "red": 0,
                "orange": 0,
                "yellow": 0,
                "green": 0,
                "high_alert": 0
            },
            "message": "No blueprint uploaded yet."
        }
    
    stats = {
        "total": len(ROOMS),
        "red": sum(1 for r in ROOMS.values() if r.get("zone") == "red"),
        "orange": sum(1 for r in ROOMS.values() if r.get("zone") == "orange"),
        "yellow": sum(1 for r in ROOMS.values() if r.get("zone") == "yellow"),
        "green": sum(1 for r in ROOMS.values() if r.get("zone") == "green"),
        "high_alert": sum(1 for r in ROOMS.values() if r.get("zone") == "high_alert"),
    }
    
    return {
        "success": True,
        "rooms": dict(ROOMS),
        "statistics": stats,
        "message": "Rooms data retrieved successfully."
    }


@app.post("/api/cameras")
def api_add_cameras(cameras: list[CameraData]):
    """Add multiple cameras for detected rooms."""
    try:
        added_count = 0
        for camera in cameras:
            # The website records a human-friendly camera name separately from
            # its room assignment.  Keep camera_name as a backwards-compatible
            # fallback for existing API callers.
            room = (camera.location or camera.camera_name).strip().upper()
            if room not in ROOMS:
                continue
            set_camera(room, camera.cloud_url)
            added_count += 1
        
        save_rooms()
        redraw()
        return {
            "success": True,
            "added": added_count,
            "message": f"Added {added_count} camera(s) successfully."
        }
    except Exception as error:
        raise HTTPException(500, f"Failed to add cameras: {str(error)}")


@app.get("/api/map-image")
def api_get_map_image():
    """Get current map image URL for website."""
    map_file = OUTPUT / "colored_output.png"
    if not STATE_FILE.exists() or not map_file.exists():
        return {
            "success": False,
            "map_url": None,
            "message": "No map available. Upload a blueprint first."
        }
    
    # Return the map file path and URL for frontend to fetch
    return {
        "success": True,
        "map_url": f"/map?t={time.time()}",
        "exists": True,
        "message": "Map image available."
    }


@app.get("/api/health")
def api_health():
    """Check API health and detector status."""
    return {
        "ok": True,
        "detector_running": True,
        "blueprint_loaded": STATE_FILE.exists() and bool(ROOMS),
        "rooms_count": len(ROOMS),
        "monitor_running": bool(camera_process and camera_process.poll() is None),
        "version": "1.0.0"
    }
