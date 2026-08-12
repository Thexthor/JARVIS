import requests
import subprocess
import datetime
import pyttsx3
import json
import webbrowser
import difflib
import os
import re
from pathlib import Path
from urllib.parse import quote_plus

try:
    import winreg
except ImportError:
    winreg = None


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "jarvis2"

MEMORY_SERVER = "http://127.0.0.1:5070"
APP_INDEX_FILE = "jarvis_apps_index.json"

LEGACY_APPS = {
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "discord": r"C:\Users\Gabo\AppData\Local\Discord\Update.exe --processStart Discord.exe",
    "spotify": r"C:\Users\Gabo\AppData\Roaming\Spotify\Spotify.exe",
    "notepad": "notepad.exe",
    "calculadora": "calc.exe",
    "explorador": "explorer.exe",
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
    "reddit": "https://www.reddit.com",
}


def normalize_name(text):
    text = (text or "").lower()
    text = re.sub(r"\.(exe|lnk|url)$", "", text)
    text = re.sub(r"[^a-záéíóúñ0-9 +#.-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class ApplicationDiscovery:
    def __init__(self):
        self.index = {}

    def add(self, name, target, source, launch_type="path"):
        if not name or not target:
            return

        key = normalize_name(name)
        if not key:
            return

        candidate = {
            "name": name.strip(),
            "target": str(target),
            "source": source,
            "launch_type": launch_type,
        }

        priority = {
            "start_menu": 4,
            "registry": 3,
            "system": 2,
            "legacy": 1,
        }

        old = self.index.get(key)

        if not old or priority.get(source, 0) > priority.get(old.get("source"), 0):
            self.index[key] = candidate

    def scan_start_menu(self):
        roots = []

        program_data = os.environ.get("PROGRAMDATA")
        app_data = os.environ.get("APPDATA")

        if program_data:
            roots.append(
                Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            )

        if app_data:
            roots.append(
                Path(app_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            )

        for root in roots:
            if not root.exists():
                continue

            try:
                for path in root.rglob("*"):
                    if path.suffix.lower() not in {".lnk", ".url"}:
                        continue

                    self.add(path.stem, path, "start_menu", "shell")
            except Exception:
                pass

    def scan_registry(self):
        if winreg is None:
            return

        locations = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"),
        ]

        for hive, root_path in locations:
            try:
                root = winreg.OpenKey(hive, root_path)
            except OSError:
                continue

            try:
                count = winreg.QueryInfoKey(root)[0]

                for i in range(count):
                    try:
                        sub_name = winreg.EnumKey(root, i)
                        sub = winreg.OpenKey(root, sub_name)
                        value, _ = winreg.QueryValueEx(sub, None)

                        self.add(
                            Path(sub_name).stem,
                            value,
                            "registry",
                            "path",
                        )
                    except Exception:
                        continue
            finally:
                try:
                    winreg.CloseKey(root)
                except Exception:
                    pass

    def add_system_tools(self):
        tools = {
            "bloc de notas": "notepad.exe",
            "notepad": "notepad.exe",
            "calculadora": "calc.exe",
            "explorador": "explorer.exe",
            "administrador de tareas": "taskmgr.exe",
            "panel de control": "control.exe",
            "powershell": "powershell.exe",
            "terminal": "wt.exe",
            "configuración": "ms-settings:",
            "configuracion": "ms-settings:",
        }

        for name, target in tools.items():
            self.add(
                name,
                target,
                "system",
                "uri" if target.endswith(":") else "path",
            )

    def add_legacy(self):
        for name, target in LEGACY_APPS.items():
            self.add(name, target, "legacy", "path")

    def build(self):
        self.index = {}
        self.scan_start_menu()
        self.scan_registry()
        self.add_system_tools()
        self.add_legacy()
        self.save()
        return self.index

    def save(self):
        with open(APP_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(self.index, f, ensure_ascii=False, indent=2)

    def load_or_build(self):
        try:
            if os.path.exists(APP_INDEX_FILE):
                with open(APP_INDEX_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, dict) and data:
                    self.index = data
                    return self.index
        except Exception:
            pass

        return self.build()

    def refresh(self):
        return self.build()

    def find(self, query):
        if not self.index:
            self.load_or_build()

        q = normalize_name(query)

        if not q:
            return None, 0.0

        if q in self.index:
            return self.index[q], 1.0

        contains = []

        for key, item in self.index.items():
            if q in key or key in q:
                score = min(len(q), len(key)) / max(len(q), len(key))
                contains.append((score, item))

        if contains:
            contains.sort(key=lambda x: x[0], reverse=True)

            if contains[0][0] >= 0.55:
                return contains[0][1], contains[0][0]

        best_item = None
        best_score = 0.0

        for key, item in self.index.items():
            score = difflib.SequenceMatcher(None, q, key).ratio()

            if score > best_score:
                best_score = score
                best_item = item

        if best_score >= 0.68:
            return best_item, best_score

        return None, best_score

    def launch(self, query):
        item, score = self.find(query)

        if not item:
            self.refresh()
            item, score = self.find(query)

        if not item:
            return {
                "ok": False,
                "respuesta": f"No encontré una aplicación que coincida con «{query}».",
                "score": score,
            }

        target = item["target"]
        launch_type = item.get("launch_type", "path")

        try:
            if launch_type in {"shell", "uri"}:
                os.startfile(target)
            else:
                if os.path.exists(target):
                    os.startfile(target)
                else:
                    subprocess.Popen(target, shell=True)

            return {
                "ok": True,
                "respuesta": f"Abriendo {item['name']}.",
                "app": item,
                "score": score,
            }
        except Exception as exc:
            return {
                "ok": False,
                "respuesta": f"No pude abrir {item['name']}: {exc}",
                "app": item,
                "score": score,
            }


app_discovery = ApplicationDiscovery()
app_discovery.load_or_build()


def strip_jarvis(text):
    return re.sub(
        r"^\s*(oye\s+|hey\s+)?jarvis\b[\s,;:.-]*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    ).strip()


def resolve_context(message):
    try:
        r = requests.post(
            f"{MEMORY_SERVER}/resolve_context",
            json={"pregunta": message},
            timeout=50,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        cleaned = strip_jarvis(message)
        return {
            "pregunta_original": message,
            "pregunta_limpia": cleaned,
            "pregunta_resuelta": cleaned,
            "vocativo": "",
            "tono": "neutral",
            "intencion": "",
            "relacion": "",
            "entidad_principal": "",
        }


def commit_turn(user, jarvis, resolved):
    try:
        requests.post(
            f"{MEMORY_SERVER}/commit_turn",
            json={
                "usuario": user,
                "jarvis": jarvis,
                "resolved": resolved,
            },
            timeout=5,
        )
    except Exception:
        pass


OPEN_PATTERNS = re.compile(
    r"^\s*(?:abre|abrir|inicia|iniciar|ejecuta|ejecutar|lanza|lanzar)\s+(.+?)\s*$",
    flags=re.IGNORECASE,
)


def try_open_app(text):
    match = OPEN_PATTERNS.match(text.strip())

    if not match:
        return None

    app_name = match.group(1).strip()
    result = app_discovery.launch(app_name)
    return result["respuesta"]


def buscar_youtube(texto):
    webbrowser.open(
        f"https://www.youtube.com/results?search_query={quote_plus(texto)}"
    )
    return f"Buscando {texto} en YouTube."


def procesar_web(mensaje):
    low = mensaje.lower()

    if "youtube" in low and any(
        p in low for p in ["busca", "buscar", "pon", "investiga"]
    ):
        query = re.sub(
            r"^(busca|buscar|pon|investiga)\s+",
            "",
            mensaje,
            flags=re.IGNORECASE,
        )
        query = re.sub(r"\s+en youtube\s*$", "", query, flags=re.IGNORECASE)
        return buscar_youtube(query), True

    return "", False


def hablar(texto):
    voz = pyttsx3.init()
    voces = voz.getProperty("voices")

    if len(voces) > 2:
        voz.setProperty("voice", voces[2].id)

    voz.setProperty("rate", 170)
    voz.say(texto)
    voz.runAndWait()
    voz.stop()


def personality_instruction(resolved):
    return f"""
Identidad:
- Eres JARVIS: elegante, seguro, leal, tecnológico y rápido.
- Tienes sarcasmo seco e inteligente, pero ocasional.
- Nunca conviertas cada respuesta en un chiste.
- Si el usuario usa un vocativo/apodo contigo, puedes reaccionar brevemente
  si encaja, pero no confundas el apodo con el tema.
- Si el tono del usuario es frustrado, reduce el sarcasmo.
- No uses emojis salvo que te los pidan.
- Responde siempre en español.

Tono detectado: {resolved.get("tono", "neutral")}
Vocativo detectado: {resolved.get("vocativo") or "(ninguno)"}
"""


def ask_ollama(original, resolved):
    prompt = f"""
{personality_instruction(resolved)}

Petición original:
{original}

Petición semánticamente resuelta:
{resolved.get("pregunta_resuelta", original)}

Intención detectada:
{resolved.get("intencion", "")}

Relación solicitada:
{resolved.get("relacion", "")}

Entidad principal:
{resolved.get("entidad_principal", "")}

REGLAS:
- Responde a la relación solicitada, no a otra.
- Usa el contexto resuelto solo cuando haga falta.
- Si no conoces un dato actual, no inventes.
- Sé natural y útil.
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "20m",
                "options": {
                    "temperature": 0.25,
                    "num_predict": 600,
                    "num_ctx": 4096,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as exc:
        return f"No pude conectar con Ollama. Error: {exc}"


def procesar(mensaje_original):
    resolved = resolve_context(mensaje_original)
    mensaje = (
        resolved.get("pregunta_resuelta")
        or resolved.get("pregunta_limpia")
        or mensaje_original
    )

    low = mensaje.lower().strip()

    if low == "salir":
        return "Cerrando sistema.", True, resolved

    if "qué hora es" in low or "que hora es" in low:
        hora = datetime.datetime.now().strftime("%I:%M %p")
        return f"Son las {hora}.", False, resolved

    if "actualiza" in low and "aplicaciones" in low:
        count = len(app_discovery.refresh())
        return f"Índice de aplicaciones actualizado. Detecté {count} entradas.", False, resolved

    app_answer = try_open_app(mensaje)
    if app_answer:
        return app_answer, False, resolved

    web_answer, handled = procesar_web(mensaje)
    if handled:
        return web_answer, False, resolved

    return ask_ollama(mensaje_original, resolved), False, resolved


if __name__ == "__main__":
    print("")
    print("====================================================")
    print("              JARVIS CORE CLI v3.0")
    print("====================================================")
    print(f"Apps indexadas: {len(app_discovery.index)}")
    print("App Discovery : Start Menu + Registro + Sistema")
    print("Contexto      : Memory Server /resolve_context")
    print("LLM           : jarvis2")
    print("====================================================")
    print("")

    while True:
        message = input("Tú: ").strip()

        if not message:
            continue

        answer, close, resolved = procesar(message)
        print("Jarvis:", answer)

        commit_turn(message, answer, resolved)
        hablar(answer)

        if close:
            break
