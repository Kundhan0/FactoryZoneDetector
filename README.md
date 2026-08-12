# Factory Zone Detector

The program first reads a labelled blueprint, creates a coloured zone map, then
checks every camera assigned to a room. A confirmed fire or smoke detection
changes only that room to the black **high_alert** zone and rewrites both `output/colored_output.png`
and `output/zones.json`.

## Install

```powershell
python -m pip install -r requirements.txt
```

Install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) as well
(it is the program that reads room labels from the blueprint). Add its install
folder to `PATH`, or use the normal Windows default location.

## Run

First discover rooms from the blueprint. This writes the detected room name,
rectangle, initial risk zone, camera field, and status into `rooms.py`.

```powershell
python detect_zones.py input/blueprint.png
```

Assign one or more cameras and run all of them. Sources may be video file
paths, YouTube links, or later RTSP/HTTP live-feed URLs. Room names must match
the names generated in `rooms.py`.

```powershell
python monitor.py input/blueprint.png `
  --camera "OFFICES=https://www.youtube.com/shorts/9qhfEc7oEjw" `
  --camera "KITCHEN=videos/kitchen.mp4" --show
```

Assignments are saved into `rooms.py`. On later runs, omit `--camera` and all
saved cameras are processed. A video ends naturally after it has been scanned;
a live RTSP/HTTP source continues until its connection ends.
`--show` opens the camera preview; press `q` to stop the current preview and
move to the next configured room camera.

`output/colored_output.png` is the visual map. `output/zones.json` contains
the current rooms, cameras, statuses, alerts, and zone counts for a dashboard
or API.

## Website API

Run the API server:

```powershell
uvicorn api:app --reload
```

Open `http://127.0.0.1:8000/docs` in a browser. It provides a page where you
can upload the blueprint, enter a room name and camera link, and start cameras
without writing frontend code. Your website can use these endpoints:

- `POST /blueprint` — multipart field `file` containing the blueprint image.
- `GET /zones` — current room/camera/status data as JSON.
- `POST /cameras` — JSON: `{"room_name":"OFFICES","source":"rtsp://..."}`.
- `DELETE /cameras/OFFICES` — remove a room camera.
- `POST /monitor/start` — JSON `{}` for all cameras, or `{"room_name":"OFFICES"}` for one. It opens an OpenCV preview for each camera by default; add `"show": false` for a website/server-only run.
- `GET /monitor/status` — rooms currently being scanned; poll this while monitoring.
- `POST /alerts/test` — forces a room to high_alert, solely to test map/dashboard updating.
- `GET /map` — latest coloured blueprint PNG.

The map changes to magenta high_alert only after a confirmed fire/smoke event (10 consecutive
detection frames by default). Refresh your website image after polling `/zones`,
for example set its image source to `/map?t=` plus `Date.now()`; this avoids a
browser displaying a cached map.

To confirm setup before using actual fire footage, call `POST /alerts/test` with
`{"room_name":"OFFICES", "event":"FIRE"}`. The response includes
`map_updated_at`; the selected room must be magenta in `GET /map` and have
`"status":"ALERT"` in `GET /zones`.

For the simplest operation, open `http://127.0.0.1:8000/` instead of the API
docs: upload a blueprint, paste camera links next to the detected rooms, and
click **Save Cameras and Start Detection**. It opens one OpenCV window for each
available camera. Zone data is always stored in `output/zones.json`.

## Test one YouTube video

```powershell
python detect_youtube.py "https://www.youtube.com/shorts/9qhfEc7oEjw"
```

This opens a standalone OpenCV window and prints confirmed detections. In the
multi-camera runner, press `q` to close the current camera and open the next.
YouTube videos are downloaded once to `output/camera_cache/` before OpenCV
opens them; this is required because OpenCV cannot reliably read YouTube's
temporary streaming URL on Windows.
