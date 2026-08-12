from flask import Flask, Response, jsonify, send_file
from flask_cors import CORS
import cv2
import os
import requests
import base64
from datetime import datetime


app = Flask(__name__)
CORS(app)

camera = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURE_DIR = os.path.join(BASE_DIR, "captures")

os.makedirs(CAPTURE_DIR, exist_ok=True)


# ==================================================
# CAMARA
# ==================================================

def iniciar_camara():
    global camera

    if camera is None:
        camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    return camera


# ==================================================
# VIDEO EN VIVO
# ==================================================

def generar_video():
    cam = iniciar_camara()

    while True:
        ok, frame = cam.read()

        if not ok:
            continue

        ok_jpg, buffer = cv2.imencode(".jpg", frame)

        if not ok_jpg:
            continue

        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame_bytes
            + b"\r\n"
        )


# ==================================================
# CAPTURAR IMAGEN
# ==================================================

def capturar_imagen():
    cam = iniciar_camara()

    if not cam.isOpened():
        return None, None

    ok, frame = cam.read()

    if not ok:
        return None, None

    # Imagen reducida para que Moondream trabaje más rápido
    frame = cv2.resize(frame, (336, 252))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"jarvis_capture_{timestamp}.jpg"
    filepath = os.path.join(CAPTURE_DIR, filename)

    guardado = cv2.imwrite(filepath, frame)

    if not guardado:
        return None, None

    return filepath, filename


# ==================================================
# VIDEO
# ==================================================

@app.route("/video")
def video():
    return Response(
        generar_video(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# ==================================================
# STATUS
# ==================================================

@app.route("/status")
def status():
    cam = iniciar_camara()

    return jsonify({
        "ok": cam.isOpened(),
        "camera_open": cam.isOpened()
    })


# ==================================================
# CAPTURA
# ==================================================

@app.route("/capture")
def capture():
    filepath, filename = capturar_imagen()

    if not filepath:
        return jsonify({
            "ok": False,
            "error": "No pude capturar una imagen."
        }), 500

    return jsonify({
        "ok": True,
        "message": "Captura realizada.",
        "filename": filename,
        "path": filepath,
        "url": f"http://127.0.0.1:5080/capture_image/{filename}"
    })


# ==================================================
# MOSTRAR CAPTURA
# ==================================================

@app.route("/capture_image/<filename>")
def capture_image(filename):
    filepath = os.path.join(CAPTURE_DIR, filename)

    if not os.path.exists(filepath):
        return jsonify({
            "ok": False,
            "error": "La imagen no existe."
        }), 404

    return send_file(
        filepath,
        mimetype="image/jpeg"
    )


# ==================================================
# ANALIZAR CON MOONDREAM
# ==================================================

@app.route("/analyze")
def analyze():
    try:

        # ------------------------------------------
        # Capturar fotografía
        # ------------------------------------------

        filepath, filename = capturar_imagen()

        if not filepath:
            return jsonify({
                "ok": False,
                "error": "No pude capturar una imagen."
            }), 500

        print("Imagen capturada:", filename)


        # ------------------------------------------
        # Convertir fotografía a Base64
        # ------------------------------------------

        with open(filepath, "rb") as image_file:
            image_base64 = base64.b64encode(
                image_file.read()
            ).decode("utf-8")


        # ------------------------------------------
        # Prompt de visión
        # ------------------------------------------

        prompt_vision = (
            "Describe brevemente lo que ves en esta imagen. "
            "Menciona solamente los elementos claramente visibles. "
            "No inventes detalles. "
            "Responde en español."
        )


        # ------------------------------------------
        # Solicitud a Moondream
        # ------------------------------------------

        payload = {
            "model": "qwen2.5vl:3b",
            "prompt": prompt_vision,
            "images": [image_base64],
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "num_predict": 60,
                "temperature": 0.0,
                "num_ctx": 4096
            }
        }


        print("Enviando imagen a llava...")

        response = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json=payload,
            timeout=180
        )


        # ------------------------------------------
        # Comprobar respuesta
        # ------------------------------------------

        if response.status_code != 200:
            print("ERROR OLLAMA:")
            print(response.text)

            return jsonify({
                "ok": False,
                "error": "Ollama devolvió un error.",
                "detalle": response.text
            }), 500


        # ------------------------------------------
        # Leer respuesta
        # ------------------------------------------

        data = response.json()

        respuesta = data.get(
            "response",
            "No pude interpretar lo que estoy viendo."
        ).strip()

        print("RESPUESTA llava:")
        print(respuesta)


        # ------------------------------------------
        # Enviar respuesta a Jarvis
        # ------------------------------------------

        return jsonify({
            "ok": True,
            "filename": filename,
            "respuesta": respuesta
        })


    except requests.exceptions.Timeout:

        print("ERROR: llava tardó demasiado.")

        return jsonify({
            "ok": False,
            "error": "Moondream tardó demasiado en responder."
        }), 504


    except requests.exceptions.ConnectionError:

        print("ERROR: No pude conectar con Ollama.")

        return jsonify({
            "ok": False,
            "error": "No pude conectar con Ollama."
        }), 503


    except Exception as error:

        print("ERROR ANALIZANDO:")
        print(error)

        return jsonify({
            "ok": False,
            "error": str(error)
        }), 500


# ==================================================
# DETENER CAMARA
# ==================================================

@app.route("/stop")
def stop():
    global camera

    if camera is not None:
        camera.release()
        camera = None

    return jsonify({
        "ok": True,
        "message": "Cámara detenida."
    })


# ==================================================
# INICIAR SERVIDOR
# ==================================================

if __name__ == "__main__":

    print("")
    print("====================================")
    print("       JARVIS VISION SERVER")
    print("====================================")
    print("Servidor : http://127.0.0.1:5080")
    print("Video    : http://127.0.0.1:5080/video")
    print("Captura  : http://127.0.0.1:5080/capture")
    print("Analizar : http://127.0.0.1:5080/analyze")
    print("Modelo   : Moondream")
    print("====================================")
    print("")

    app.run(
        host="127.0.0.1",
        port=5080,
        threaded=True
    )
