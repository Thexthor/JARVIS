import subprocess
import time
import os

COLAB_URL = "https://colab.research.google.com/drive/1KgBAbfff5ZP2TxecSm-LqTEkdxWiDKaE"

OPERA_GX_PATHS = [
    r"C:\Users\Gabo\AppData\Local\Programs\Opera GX\opera.exe",
    r"C:\Users\Gabo\AppData\Local\Programs\Opera GX\launcher.exe",
    r"C:\Program Files\Opera GX\opera.exe",
    r"C:\Program Files\Opera GX\launcher.exe",
]

opera_path = None

for path in OPERA_GX_PATHS:
    if os.path.exists(path):
        opera_path = path
        break

if not opera_path:
    print("No encontré Opera GX.")
    raise SystemExit

subprocess.Popen([
    opera_path,
    "--start-minimized",
    COLAB_URL
])

print(f"Opera GX abrió Colab usando: {opera_path}")

while True:
    time.sleep(60)
