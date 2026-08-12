import cv2
import numpy as np
import pygame
import yt_dlp

pygame.mixer.init()

# -------------------------
# SETTINGS
# -------------------------

VIDEO_URL = "https://www.youtube.com/shorts/9qhfEc7oEjw"

ALARM_SOUND = "mixkit-facility-alarm-sound-999.wav"

MIN_FIRE_AREA = 2000
MIN_SMOKE_AREA = 3000

FIRE_CONFIRM_FRAMES = 10
SMOKE_CONFIRM_FRAMES = 15

# -------------------------
# GET DIRECT VIDEO STREAM
# -------------------------

def get_video_stream(url):

    ydl_opts = {
        "quiet": True,
        "format": "best"
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(url, download=False)

        return info["url"]


stream_url = get_video_stream(VIDEO_URL)

cap = cv2.VideoCapture(stream_url)

# -------------------------
# FIRE HSV RANGES
# -------------------------

lower_fire1 = np.array([0, 120, 70])
upper_fire1 = np.array([10, 255, 255])

lower_fire2 = np.array([170, 120, 70])
upper_fire2 = np.array([180, 255, 255])

# -------------------------
# BACKGROUND SUBTRACTOR
# -------------------------

bg_subtractor = cv2.createBackgroundSubtractorMOG2(
    history=500,
    varThreshold=50,
    detectShadows=False
)

fire_frames = 0
smoke_frames = 0

alarm_active = False

while True:

    ret, frame = cap.read()

    if not ret:
        break

    frame = cv2.resize(frame, (1280, 720))

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # ==================================
    # FIRE DETECTION
    # ==================================

    fire_mask1 = cv2.inRange(
        hsv,
        lower_fire1,
        upper_fire1
    )

    fire_mask2 = cv2.inRange(
        hsv,
        lower_fire2,
        upper_fire2
    )

    fire_mask = cv2.bitwise_or(
        fire_mask1,
        fire_mask2
    )

    kernel = np.ones((5,5), np.uint8)

    fire_mask = cv2.morphologyEx(
        fire_mask,
        cv2.MORPH_CLOSE,
        kernel
    )

    fire_detected = False

    fire_contours, _ = cv2.findContours(
        fire_mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    for contour in fire_contours:

        area = cv2.contourArea(contour)

        if area < MIN_FIRE_AREA:
            continue

        fire_detected = True

        x, y, w, h = cv2.boundingRect(contour)

        cv2.rectangle(
            frame,
            (x, y),
            (x+w, y+h),
            (0,0,255),
            2
        )

        cv2.putText(
            frame,
            "FIRE",
            (x, y-10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0,0,255),
            2
        )

    # ==================================
    # SMOKE DETECTION
    # ==================================

    fg_mask = bg_subtractor.apply(frame)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    smoke_mask = cv2.inRange(
        gray,
        120,
        255
    )

    smoke_mask = cv2.bitwise_and(
        smoke_mask,
        fg_mask
    )

    smoke_detected = False

    smoke_contours, _ = cv2.findContours(
        smoke_mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    for contour in smoke_contours:

        area = cv2.contourArea(contour)

        if area < MIN_SMOKE_AREA:
            continue

        smoke_detected = True

        x, y, w, h = cv2.boundingRect(contour)

        cv2.rectangle(
            frame,
            (x, y),
            (x+w, y+h),
            (255,255,0),
            2
        )

        cv2.putText(
            frame,
            "SMOKE",
            (x, y-10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255,255,0),
            2
        )

    # ==================================
    # CONFIRMATION LOGIC
    # ==================================

    if fire_detected:
        fire_frames += 1
    else:
        fire_frames = 0

    if smoke_detected:
        smoke_frames += 1
    else:
        smoke_frames = 0

    # ==================================
    # ALERT
    # ==================================

    if (
        fire_frames >= FIRE_CONFIRM_FRAMES
        or
        smoke_frames >= SMOKE_CONFIRM_FRAMES
    ):

        if not alarm_active:

            pygame.mixer.music.load(ALARM_SOUND)
            pygame.mixer.music.play()

            alarm_active = True

            print("ALERT: FIRE OR SMOKE DETECTED")

    if fire_frames >= FIRE_CONFIRM_FRAMES:

        cv2.putText(
            frame,
            "FIRE DETECTED",
            (20,50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0,0,255),
            3
        )

    if smoke_frames >= SMOKE_CONFIRM_FRAMES:

        cv2.putText(
            frame,
            "SMOKE DETECTED",
            (20,100),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255,255,0),
            3
        )

    cv2.imshow(
        "Fire & Smoke Detection",
        frame
    )

    key = cv2.waitKey(1)

    if key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
pygame.mixer.quit()