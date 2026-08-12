import cv2
import numpy as np
import pytesseract
from config import ZONE_KEYWORDS

# Change if needed
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

ZONE_COLORS = {
    "red": (0,0,255),
    "orange": (0,165,255),
    "yellow": (0,255,255),
    "green": (0,255,0)
}

def classify_zone(text):
    t = text.lower()
    for zone, words in ZONE_KEYWORDS.items():
        for w in words:
            if w in t:
                return zone
    return None

def process_blueprint(image_path, output_path):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(image_path)

    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    counts = {"red":0,"orange":0,"yellow":0,"green":0}
    overlay = img.copy()

    n = len(data["text"])

    for i in range(n):
        text = data["text"][i].strip()
        if not text:
            continue

        zone = classify_zone(text)
        if zone is None:
            continue

        x,y,w,h = (data["left"][i], data["top"][i],
                   data["width"][i], data["height"][i])

        pad = 120
        x1=max(0,x-pad)
        y1=max(0,y-pad)
        x2=min(img.shape[1],x+w+pad)
        y2=min(img.shape[0],y+h+pad)

        cv2.rectangle(overlay,(x1,y1),(x2,y2),ZONE_COLORS[zone],-1)
        cv2.rectangle(img,(x1,y1),(x2,y2),ZONE_COLORS[zone],3)
        counts[zone]+=1

    result = cv2.addWeighted(overlay,0.35,img,0.65,0)

    total=sum(counts.values())
    print("\\n===== FACTORY ZONE REPORT =====")
    for k,v in counts.items():
        pct=(v/total*100) if total else 0
        print(f"{k.upper():8}: {v} ({pct:.1f}%)")
    print("TOTAL:", total)

    cv2.imwrite(output_path,result)
    return counts

if __name__ == "__main__":
    process_blueprint("input/blueprint2.png","output/colored_output.png")
