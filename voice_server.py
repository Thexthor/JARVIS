from flask import Flask, request, jsonify
from flask_cors import CORS
import edge_tts
import asyncio
import tempfile
import subprocess

app = Flask(__name__)
CORS(app)

VOICE = "es-MX-JorgeNeural"
RATE = "+0%"
PITCH = "+0Hz"

current_player = None


async def generar_audio(texto, output_path):
    communicate = edge_tts.Communicate(
        text=texto,
        voice=VOICE,
        rate=RATE,
        pitch=PITCH
    )
    await communicate.save(output_path)


def detener_audio_actual():
    global current_player

    if current_player and current_player.poll() is None:
        try:
            current_player.terminate()
        except:
            pass

    current_player = None


@app.route("/speak", methods=["POST"])
def speak():
    global current_player

    try:
        detener_audio_actual()

        data = request.get_json()
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"ok": False, "error": "Texto vacío"})

        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        output_path = temp_audio.name
        temp_audio.close()

        print(f"Hablando: {text}")

        asyncio.run(generar_audio(text, output_path))

        ps_script = f"""
Add-Type -AssemblyName presentationCore
$player = New-Object System.Windows.Media.MediaPlayer
$player.Open([System.Uri]::new('{output_path}'))
Start-Sleep -Milliseconds 300
$player.Play()

while ($player.NaturalDuration.HasTimeSpan -eq $false) {{
    Start-Sleep -Milliseconds 100
}}

$duration = $player.NaturalDuration.TimeSpan.TotalSeconds
Start-Sleep -Seconds $duration
$player.Close()
Remove-Item '{output_path}' -ErrorAction SilentlyContinue
"""

        current_player = subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return jsonify({"ok": True})

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"ok": False, "error": str(e)})


@app.route("/stop", methods=["POST", "GET"])
def stop():
    detener_audio_actual()
    print("Voz detenida.")
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("Voice Server Edge TTS iniciado en http://127.0.0.1:5090")
    app.run(host="127.0.0.1", port=5090)
