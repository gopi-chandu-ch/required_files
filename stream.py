import pyautogui
import io
import time
import requests
from PIL import Image
import socket
import uuid

# =========================
# CONFIGURATION
# =========================
SERVER_URL = "https://stream-au39.onrender.com/upload"
FPS = 12                    # 12–20 = smooth motion
JPEG_QUALITY = 60
TIMEOUT = 5

# Unique stream ID (auto-generated)
STREAM_ID = f"{socket.gethostname()}_{uuid.uuid4().hex[:6]}"

print("📡 Screen streaming client started...")
print(f"🆔 Stream ID: {STREAM_ID}")
print(f"➡️ Sending frames to: {SERVER_URL}")

# =========================
# SCREEN CAPTURE FUNCTION
# =========================
def capture_screen():
    screenshot = pyautogui.screenshot()

    # Optional: resize for speed (recommended)
    screenshot = screenshot.resize((1280, 720))

    buffer = io.BytesIO()
    screenshot.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    buffer.seek(0)

    return buffer.getvalue()

# =========================
# MAIN LOOP
# =========================
while True:
    try:
        frame = capture_screen()

        files = {
            "frame": ("screen.jpg", frame, "image/jpeg")
        }

        data = {
            "stream_id": STREAM_ID
        }

        response = requests.post(
            SERVER_URL,
            files=files,
            data=data,
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            print("⚠️ Server response:", response.text)

    except Exception as e:
        print("❌ Error:", e)

    time.sleep(1 / FPS)
