import pyautogui
import io
import time
import requests
from PIL import Image

# =========================
# CONFIGURATION
# =========================
SERVER_URL = "https://stream-au39.onrender.com/upload"
FPS = 10
JPEG_QUALITY = 70
TIMEOUT = 5

print("📡 Screen streaming client started...")
print(f"➡️ Sending frames to: {SERVER_URL}")

# =========================
# SCREEN CAPTURE FUNCTION
# =========================
def capture_screen():
    """
    Capture the current screen and return JPEG bytes
    """
    screenshot = pyautogui.screenshot()

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

        response = requests.post(
            SERVER_URL,
            files=files,
            timeout=TIMEOUT
        )

        if response.status_code != 200:
            print("⚠️ Server response:", response.text)

    except Exception as e:
        print("❌ Error:", e)

    time.sleep(1 / FPS)
