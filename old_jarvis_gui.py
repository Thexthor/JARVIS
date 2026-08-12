import tkinter as tk
from tkinter import scrolledtext
import requests
import subprocess
import datetime
import pyttsx3
import threading
import json
import webbrowser
import difflib
from urllib.parse import quote_plus

url = "http://localhost:11434/api/generate"
MEMORY_FILE = "memory.json"

APPS = {
    "chrome": {"comando": r"C:\Program Files\Google\Chrome\Application\chrome.exe", "shell": False, "frases": ["chrome", "crome", "cron", "google chrome"]},
    "discord": {"comando": r"C:\Users\Gabo\AppData\Local\Discord\Update.exe --processStart Discord.exe", "shell": False, "frases": ["discord", "discor"]},
    "spotify": {"comando": r"C:\Users\Gabo\AppData\Roaming\Spotify\Spotify.exe", "shell": False, "frases": ["spotify", "musica", "música"]},
    "notepad": {"comando": "notepad.exe", "shell": False, "frases": ["notepad", "bloc", "bloc de notas"]},
    "calculadora": {"comando": "calc.exe", "shell": False, "frases": ["calculadora", "calculator"]},
    "explorador": {"comando": "explorer.exe", "shell": False, "frases": ["explorador", "archivos", "carpetas"]}
}

SITIOS = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "chatgpt": "https://chatgpt.com",
    "open webui": "http://localhost:3000",
    "github": "https://github.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "reddit": "https://www.reddit.com"
}

def cargar_memoria():
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"recuerdos": []}

def guardar_memoria(memoria):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memoria, f, indent=4, ensure_ascii=False)

def agregar_recuerdo(texto):
    memoria = cargar_memoria()
    memoria.setdefault("recuerdos", [])
    memoria["recuerdos"].append(texto)
    guardar_memoria(memoria)

def obtener_recuerdos():
    recuerdos = cargar_memoria().get("recuerdos", [])
    if not recuerdos:
        return "No recuerdo nada todavía."
    return "\n".join(recuerdos)

def hablar(texto):
    voz = pyttsx3.init()
    voces = voz.getProperty("voices")
    if len(voces) > 2:
        voz.setProperty("voice", voces[2].id)
    voz.setProperty("rate", 170)
    voz.say(texto)
    voz.runAndWait()
    voz.stop()

def limpiar_texto(texto):
    texto = texto.lower().strip()
    texto = texto.replace(".", "")
    texto = texto.replace(",", "")
    texto = texto.replace("jarvis", "")
    texto = texto.replace("por favor", "")
    return texto.strip()

def abrir_app(nombre_app):
    app = APPS[nombre_app]
    subprocess.Popen(app["comando"], shell=app["shell"])
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
    texto = texto.replace("en google", "").replace("google", "").replace("a ", "", 1).strip()
    webbrowser.open(f"https://www.google.com/search?q={quote_plus(texto)}")
    return f"Buscando {texto} en Google."

def buscar_youtube(texto):
    texto = texto.replace("en youtube", "").replace("youtube", "").replace("a ", "", 1).strip()
    webbrowser.open(f"https://www.youtube.com/results?search_query={quote_plus(texto)}")
    return f"Buscando {texto} en YouTube."

def procesar_web(mensaje):
    if "youtube" in mensaje and any(p in mensaje for p in ["busca", "buscar", "pon", "investiga"]):
        for palabra in ["busca", "buscar", "pon", "investiga"]:
            if palabra in mensaje:
                return buscar_youtube(mensaje.split(palabra, 1)[1].strip()), True

    if any(p in mensaje for p in ["busca", "buscar", "búscame", "buscame", "investiga"]):
        for palabra in ["busca", "buscar", "búscame", "buscame", "investiga"]:
            if palabra in mensaje:
                return buscar_google(mensaje.split(palabra, 1)[1].strip()), True

    nombre, url_sitio = detectar_sitio(mensaje)
    if nombre:
        return abrir_sitio(nombre, url_sitio), True

    return "", False

def respuesta_local(mensaje_original):
    mensaje = limpiar_texto(mensaje_original)

    saludos = [
        "hola", "holi", "que lo que", "qué lo que", "buenas",
        "saludos", "hey", "ey", "bro", "mano", "klk",
        "hello", "hi", "buen dia", "buen día",
        "buenas tardes", "buenas noches"
    ]

    if any(saludo in mensaje for saludo in saludos):
        return "Qué lo que, Gabo. ¿Qué hacemos hoy?", False, True

    if mensaje == "salir":
        return "Cerrando sistema.", True, True

    if mensaje.startswith("di "):
        return mensaje_original.strip()[3:], False, True

    if "hora" in mensaje:
        hora = datetime.datetime.now().strftime("%I:%M %p")
        return f"Son las {hora}.", False, True

    if "recuerda que" in mensaje:
        recuerdo = mensaje.split("recuerda que", 1)[1].strip()
        if recuerdo:
            agregar_recuerdo(recuerdo)
            return "Lo recordaré.", False, True
        return "No entendí qué debo recordar.", False, True

    if "qué recuerdas de mí" in mensaje or "que recuerdas de mi" in mensaje:
        return obtener_recuerdos(), False, True

    respuesta_web, manejado = procesar_web(mensaje)
    if manejado:
        return respuesta_web, False, True

    if any(p in mensaje for p in ["abre", "abrir", "inicia", "iniciar", "ejecuta", "lanza"]):
        app = detectar_app(mensaje)
        if app:
            return abrir_app(app), False, True
        return "No reconozco esa aplicación todavía.", False, True

    return "", False, False

def construir_prompt(mensaje_original):
    memoria = cargar_memoria()
    contexto_memoria = "\n".join(memoria.get("recuerdos", []))

    return f"""
Eres Jarvis 2.0, asistente de Gabo.

Recuerdos importantes:
{contexto_memoria}

Instrucciones:
- Responde natural.
- Sé útil.
- Si es una tarea o explicación, responde claro.
- No entres en crisis por saludos o frases casuales.
- Si no sabes algo, dilo normal.

Usuario:
{mensaje_original}
"""

def enviar_mensaje():
    mensaje = entrada.get().strip()
    entrada.delete(0, tk.END)

    if not mensaje:
        return

    chat.insert(tk.END, f"Tú: {mensaje}\n")
    chat.insert(tk.END, "Jarvis: ")
    chat.see(tk.END)

    threading.Thread(target=procesar_en_hilo, args=(mensaje,), daemon=True).start()

def procesar_en_hilo(mensaje):
    respuesta, cerrar, manejado = respuesta_local(mensaje)

    if manejado:
        ventana.after(0, lambda: escribir_texto(respuesta + "\n\n"))
        hablar(respuesta)

        if cerrar:
            ventana.after(1000, ventana.destroy)
        return

    prompt = construir_prompt(mensaje)

    datos = {
        "model": "jarvis2",
        "prompt": prompt,
        "stream": True,
        "options": {
            "num_predict": 300
        }
    }

    respuesta_completa = ""

    try:
        with requests.post(url, json=datos, stream=True) as r:
            for linea in r.iter_lines():
                if linea:
                    data = json.loads(linea.decode("utf-8"))
                    pedazo = data.get("response", "")

                    if pedazo:
                        respuesta_completa += pedazo
                        ventana.after(0, lambda t=pedazo: escribir_texto(t))

                    if data.get("done", False):
                        break

    except Exception as error:
        respuesta_completa = f"No pude conectar con Ollama. Error: {error}"
        ventana.after(0, lambda: escribir_texto(respuesta_completa))

    ventana.after(0, lambda: escribir_texto("\n\n"))

    if respuesta_completa.strip():
        hablar(respuesta_completa)

def escribir_texto(texto):
    chat.insert(tk.END, texto)
    chat.see(tk.END)

ventana = tk.Tk()
ventana.title("Jarvis 2.0")
ventana.geometry("850x600")
ventana.configure(bg="#0b0f14")

titulo = tk.Label(
    ventana,
    text="JARVIS 2.0",
    font=("Arial", 24, "bold"),
    bg="#0b0f14",
    fg="#00ffcc"
)
titulo.pack(pady=10)

estado = tk.Label(
    ventana,
    text="Sistema activo · Memoria conectada · Streaming activado",
    font=("Arial", 10),
    bg="#0b0f14",
    fg="#9fffe8"
)
estado.pack()

chat = scrolledtext.ScrolledText(
    ventana,
    wrap=tk.WORD,
    font=("Consolas", 11),
    bg="#111820",
    fg="white",
    insertbackground="white",
    borderwidth=0
)
chat.pack(padx=20, pady=15, fill=tk.BOTH, expand=True)

entrada = tk.Entry(
    ventana,
    font=("Arial", 13),
    bg="#1c2733",
    fg="white",
    insertbackground="white",
    borderwidth=0
)
entrada.pack(padx=20, pady=5, fill=tk.X, ipady=8)

boton = tk.Button(
    ventana,
    text="Enviar",
    command=enviar_mensaje,
    font=("Arial", 12, "bold"),
    bg="#00ffcc",
    fg="black",
    borderwidth=0
)
boton.pack(pady=10)

entrada.bind("<Return>", lambda event: enviar_mensaje())

chat.insert(tk.END, "Jarvis: Sistema iniciado. Memoria y streaming activos.\n\n")

ventana.mainloop()
