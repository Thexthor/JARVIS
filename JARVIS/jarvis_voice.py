import requests
import subprocess
import datetime
import pyttsx3
import sounddevice as sd
import webbrowser
import difflib
import numpy as np
import json
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
from urllib.parse import quote_plus

url = "http://localhost:11434/api/generate"

modelo_whisper = WhisperModel(
    "small",
    compute_type="int8"
)

MEMORY_FILE = "memory.json"

APPS = {
    "chrome": {
        "comando": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "shell": False,
        "frases": [
            "chrome",
            "crome",
            "cron",
            "google chrome"
        ]
    },

    "discord": {
        "comando": r"C:\Users\Gabo\AppData\Local\Discord\Update.exe --processStart Discord.exe",
        "shell": False,
        "frases": [
            "discord"
        ]
    },

    "spotify": {
        "comando": r"C:\Users\Gabo\AppData\Roaming\Spotify\Spotify.exe",
        "shell": False,
        "frases": [
            "spotify"
        ]
    },

    "notepad": {
        "comando": "notepad.exe",
        "shell": False,
        "frases": [
            "notepad",
            "bloc"
        ]
    }
}

SITIOS = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "chatgpt": "https://chatgpt.com",
    "github": "https://github.com",
    "instagram": "https://www.instagram.com"
}

def cargar_memoria():

    try:

        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except:
        return {"recuerdos": []}

def guardar_memoria(memoria):

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(
            memoria,
            f,
            indent=4,
            ensure_ascii=False
        )

def agregar_recuerdo(texto):

    memoria = cargar_memoria()

    memoria["recuerdos"].append(texto)

    guardar_memoria(memoria)

def obtener_recuerdos():

    memoria = cargar_memoria()

    recuerdos = memoria.get("recuerdos", [])

    if not recuerdos:
        return "No recuerdo nada todavía."

    return "\n".join(recuerdos)

def hablar(texto):

    voz = pyttsx3.init()

    voces = voz.getProperty("voices")

    if len(voces) > 2:
        voz.setProperty("voice", voces[2].id)

    voz.setProperty("rate", 180)

    voz.say(texto)

    voz.runAndWait()

    voz.stop()

def limpiar_texto(texto):

    texto = texto.lower().strip()

    texto = texto.replace(".", "")
    texto = texto.replace(",", "")
    texto = texto.replace("jarvis", "")

    return texto.strip()

def escuchar():

    frecuencia = 16000
    bloque = 1024

    umbral_voz = 250
    silencio_maximo = 25

    audio_total = []

    silencio = 0
    empezo_a_hablar = False

    print("Escuchando...")

    with sd.InputStream(
        samplerate=frecuencia,
        channels=1,
        dtype="int16",
        blocksize=bloque
    ) as stream:

        while True:

            audio, overflowed = stream.read(
                bloque
            )

            volumen = np.abs(audio).mean()

            if volumen > umbral_voz:

                empezo_a_hablar = True

                silencio = 0

                audio_total.append(
                    audio.copy()
                )

            elif empezo_a_hablar:

                silencio += 1

                audio_total.append(
                    audio.copy()
                )

                if silencio > silencio_maximo:
                    break

    if not audio_total:
        return ""

    audio_final = np.concatenate(
        audio_total,
        axis=0
    )

    write(
        "voz_usuario.wav",
        frecuencia,
        audio_final
    )

    segmentos, info = modelo_whisper.transcribe(
        "voz_usuario.wav",
        language="es",
        condition_on_previous_text=False,
        beam_size=1,
        best_of=1
    )

    texto = ""

    for segmento in segmentos:
        texto += segmento.text

    texto = texto.strip()

    return texto

def abrir_app(nombre_app):

    app = APPS[nombre_app]

    subprocess.Popen(
        app["comando"],
        shell=app["shell"]
    )

    return f"Abriendo {nombre_app}."

def detectar_app(mensaje):

    for nombre_app, config in APPS.items():

        for frase in config["frases"]:

            if frase in mensaje:
                return nombre_app

    return None

def detectar_sitio(mensaje):

    for nombre, url_sitio in SITIOS.items():

        if nombre in mensaje:
            return nombre, url_sitio

    return None, None

def abrir_sitio(nombre, url_sitio):

    webbrowser.open(url_sitio)

    return f"Abriendo {nombre}."

def buscar_google(texto):

    texto = texto.replace(
        "en google",
        ""
    ).replace(
        "google",
        ""
    ).strip()

    webbrowser.open(
        f"https://www.google.com/search?q={quote_plus(texto)}"
    )

    return f"Buscando {texto} en Google."

def procesar_web(mensaje):

    if any(
        p in mensaje
        for p in [
            "busca",
            "buscar",
            "investiga"
        ]
    ):

        for palabra in [
            "busca",
            "buscar",
            "investiga"
        ]:

            if palabra in mensaje:

                busqueda = mensaje.split(
                    palabra,
                    1
                )[1].strip()

                return buscar_google(
                    busqueda
                ), True

    nombre, url_sitio = detectar_sitio(
        mensaje
    )

    if nombre:

        return abrir_sitio(
            nombre,
            url_sitio
        ), True

    return "", False

def procesar(mensaje_original):

    mensaje = limpiar_texto(
        mensaje_original
    )

    if mensaje == "salir":
        return "Cerrando sistema.", True

    if mensaje.startswith("di "):
        return mensaje_original.strip()[3:], False

    if "hora" in mensaje:

        hora = datetime.datetime.now().strftime(
            "%I:%M %p"
        )

        return f"Son las {hora}.", False

    if "recuerda que" in mensaje:

        recuerdo = mensaje.split(
            "recuerda que",
            1
        )[1].strip()

        agregar_recuerdo(recuerdo)

        return "Lo recordaré.", False

    if (
        "qué recuerdas de mí" in mensaje
        or "que recuerdas de mi" in mensaje
    ):

        recuerdos = obtener_recuerdos()

        return recuerdos, False

    respuesta_web, manejado = procesar_web(
        mensaje
    )

    if manejado:
        return respuesta_web, False

    if any(
        p in mensaje
        for p in [
            "abre",
            "abrir",
            "inicia"
        ]
    ):

        app = detectar_app(mensaje)

        if app:
            return abrir_app(app), False

    memoria = cargar_memoria()

    contexto_memoria = "\n".join(
        memoria["recuerdos"]
    )

    prompt = f"""
Estos son recuerdos importantes del usuario:

{contexto_memoria}

Usuario:
{mensaje_original}

Responde naturalmente.
"""

    datos = {
        "model": "jarvis2",
        "prompt": prompt,
        "stream": False
    }

    try:

        respuesta = requests.post(
            url,
            json=datos
        )

        contenido = respuesta.json()

        return contenido["response"], False

    except Exception as error:

        return (
            f"No pude conectar con Ollama. Error: {error}",
            False
        )

print("Jarvis 2.0 iniciado.")

hablar("Jarvis 2.0 iniciado.")

while True:

    mensaje = escuchar()

    if not mensaje:
        continue

    print("Tú:", mensaje)

    respuesta, cerrar = procesar(
        mensaje
    )

    print("Jarvis:", respuesta)

    hablar(respuesta)

    if cerrar:
        break
