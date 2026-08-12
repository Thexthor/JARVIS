from flask import Flask, request, jsonify
from flask_cors import CORS
from yt_dlp import YoutubeDL
import subprocess
import urllib.parse
import os
import json
import re
import difflib
from pathlib import Path

try:
    import winreg
except ImportError:
    winreg = None

app = Flask(__name__)
CORS(app)

BROWSER_PATHS = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "opera": [
        r"C:\Users\Gabo\AppData\Local\Programs\Opera\launcher.exe",
        r"C:\Users\Gabo\AppData\Local\Programs\Opera\opera.exe",
        r"C:\Users\Gabo\AppData\Local\Programs\Opera Stable\launcher.exe",
        r"C:\Users\Gabo\AppData\Local\Programs\Opera Stable\opera.exe",
        r"C:\Program Files\Opera\launcher.exe",
        r"C:\Program Files\Opera\opera.exe",
        r"C:\Program Files\Opera Stable\launcher.exe",
        r"C:\Program Files\Opera Stable\opera.exe",
    ],
    "opera gx": [
        r"C:\Users\Gabo\AppData\Local\Programs\Opera GX\launcher.exe",
        r"C:\Users\Gabo\AppData\Local\Programs\Opera GX\opera.exe",
        r"C:\Users\Gabo\AppData\Local\Programs\Opera GX Stable\launcher.exe",
        r"C:\Users\Gabo\AppData\Local\Programs\Opera GX Stable\opera.exe",
        r"C:\Program Files\Opera GX\launcher.exe",
        r"C:\Program Files\Opera GX\opera.exe",
        r"C:\Program Files\Opera GX Stable\launcher.exe",
        r"C:\Program Files\Opera GX Stable\opera.exe",
    ],
}

APP_PATHS = {
    # Se conserva como fallback de compatibilidad. La fuente principal ahora
    # es ApplicationDiscovery.
    "chrome": BROWSER_PATHS["chrome"],
    "google chrome": BROWSER_PATHS["chrome"],
    "opera": BROWSER_PATHS["opera"],
    "opera gx": BROWSER_PATHS["opera gx"],
    "whatsapp": [r"C:\Users\Gabo\AppData\Local\WhatsApp\WhatsApp.exe"],
    "discord": [r"C:\Users\Gabo\AppData\Local\Discord\Update.exe"],
    "vscode": [r"C:\Users\Gabo\AppData\Local\Programs\Microsoft VS Code\Code.exe"],
    "visual studio code": [
        r"C:\Users\Gabo\AppData\Local\Programs\Microsoft VS Code\Code.exe"
    ],
}

APP_INDEX_FILE = "jarvis_apps_index.json"


def normalizar_nombre_app(texto):
    texto = (texto or "").lower()
    texto = re.sub(r"\.(exe|lnk|url)$", "", texto)
    texto = re.sub(r"[^a-záéíóúñ0-9 +#._-]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


class ApplicationDiscovery:
    """
    Descubre aplicaciones instaladas sin tener que agregarlas una por una.

    Fuentes:
    - accesos directos del menú Inicio;
    - App Paths del Registro de Windows;
    - herramientas del sistema;
    - APP_PATHS existente como fallback.
    """

    def __init__(self):
        self.index = {}

    def add(self, name, target, source, launch_type="path", extra_args=None):
        if not name or not target:
            return

        key = normalizar_nombre_app(name)

        if not key:
            return

        candidate = {
            "name": str(name).strip(),
            "target": str(target),
            "source": source,
            "launch_type": launch_type,
            "extra_args": extra_args or [],
        }

        priority = {
            "start_menu": 5,
            "registry": 4,
            "system": 3,
            "fallback": 2,
        }

        current = self.index.get(key)

        if not current or priority.get(source, 0) > priority.get(current.get("source"), 0):
            self.index[key] = candidate

    def scan_start_menu(self):
        roots = []

        program_data = os.environ.get("PROGRAMDATA")
        app_data = os.environ.get("APPDATA")

        if program_data:
            roots.append(
                Path(program_data)
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs"
            )

        if app_data:
            roots.append(
                Path(app_data)
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs"
            )

        for root in roots:
            if not root.exists():
                continue

            try:
                for path in root.rglob("*"):
                    if path.suffix.lower() not in {".lnk", ".url"}:
                        continue

                    self.add(
                        path.stem,
                        path,
                        "start_menu",
                        "shell",
                    )
            except Exception as exc:
                print(f"[APP DISCOVERY] Start Menu: {exc}")

    def scan_registry(self):
        if winreg is None:
            return

        locations = [
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
            ),
            (
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
            ),
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths",
            ),
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
            "bloc de notas": ("notepad.exe", "path"),
            "notepad": ("notepad.exe", "path"),
            "calculadora": ("calc.exe", "path"),
            "explorador": ("explorer.exe", "path"),
            "explorador de archivos": ("explorer.exe", "path"),
            "administrador de tareas": ("taskmgr.exe", "path"),
            "panel de control": ("control.exe", "path"),
            "powershell": ("powershell.exe", "path"),
            "terminal": ("wt.exe", "path"),
            "configuración": ("ms-settings:", "uri"),
            "configuracion": ("ms-settings:", "uri"),
        }

        for name, (target, launch_type) in tools.items():
            self.add(name, target, "system", launch_type)

    def add_fallbacks(self):
        for name, paths in APP_PATHS.items():
            for path in paths:
                extra_args = []

                if name == "discord" and path.lower().endswith("update.exe"):
                    extra_args = ["--processStart", "Discord.exe"]

                self.add(
                    name,
                    path,
                    "fallback",
                    "path",
                    extra_args=extra_args,
                )

    def build(self):
        self.index = {}
        self.scan_start_menu()
        self.scan_registry()
        self.add_system_tools()
        self.add_fallbacks()
        self.save()
        return self.index

    def save(self):
        try:
            with open(APP_INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(self.index, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"[APP DISCOVERY] No pude guardar índice: {exc}")

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

    def _alias_score(self, query, key, item):
        q = normalizar_nombre_app(query)
        k = normalizar_nombre_app(key)
        n = normalizar_nombre_app(item.get("name", ""))

        if q == k or q == n:
            return 1.0

        # Ej. "obs" debe poder encontrar "obs studio".
        q_tokens = set(q.split())
        k_tokens = set(k.split())

        if q_tokens and q_tokens.issubset(k_tokens):
            return 0.94

        if q in k or k in q:
            return 0.86

        # Iniciales: "vscode", "vs code", etc.
        initials = "".join(
            token[0]
            for token in k.split()
            if token
        )

        if q == initials and len(q) >= 2:
            return 0.83

        return difflib.SequenceMatcher(None, q, k).ratio()

    def find(self, query):
        if not self.index:
            self.load_or_build()

        q = normalizar_nombre_app(query)

        if not q:
            return None, 0.0

        best = None
        best_score = 0.0

        for key, item in self.index.items():
            score = self._alias_score(q, key, item)

            if score > best_score:
                best = item
                best_score = score

        # Umbral conservador para no abrir otra aplicación por accidente.
        if best_score >= 0.72:
            return best, best_score

        return None, best_score

    def launch_item(self, item):
        target = item.get("target")
        launch_type = item.get("launch_type", "path")
        extra_args = item.get("extra_args", [])

        if not target:
            return False

        try:
            if launch_type in {"shell", "uri"}:
                os.startfile(target)
                return True

            if os.path.exists(target):
                if extra_args:
                    subprocess.Popen([target, *extra_args])
                else:
                    os.startfile(target)
                return True

            # Para comandos del sistema como calc.exe.
            subprocess.Popen([target, *extra_args], shell=False)
            return True

        except Exception as exc:
            print(f"[APP LAUNCH] {item.get('name')}: {exc}")
            return False

    def launch(self, query):
        item, score = self.find(query)

        if not item:
            # Si se instaló recientemente, refrescamos una sola vez.
            self.refresh()
            item, score = self.find(query)

        if not item:
            return False, None, score

        ok = self.launch_item(item)
        return ok, item, score



app_discovery = ApplicationDiscovery()
app_discovery.load_or_build()


# ============================================================
# FOLDER DISCOVERY ENGINE
# ============================================================

FOLDER_INDEX_FILE = "jarvis_folders_index.json"


def normalizar_nombre_carpeta(texto):
    texto = (texto or "").lower()
    texto = re.sub(r"[^a-záéíóúñ0-9 _.-]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


class FolderDiscovery:
    """
    Índice rápido y genérico de carpetas.

    No escanea todo el disco cada vez. Indexa ubicaciones comunes del usuario
    y hasta dos niveles de profundidad para mantener buena velocidad.
    """

    def __init__(self):
        self.index = {}

    def add(self, name, path, source):
        if not name or not path:
            return

        path = str(path)

        if not os.path.isdir(path):
            return

        key = normalizar_nombre_carpeta(name)

        if not key:
            return

        item = {
            "name": str(name).strip(),
            "path": path,
            "source": source,
        }

        # Evita pisar una coincidencia ya mejor ubicada.
        if key not in self.index:
            self.index[key] = item

    def _scan_root(self, root_path, source, max_depth=2):
        root = Path(root_path)

        if not root.exists() or not root.is_dir():
            return

        try:
            self.add(root.name or str(root), root, source)

            root_parts = len(root.parts)

            for current_root, dirs, _ in os.walk(root):
                current = Path(current_root)
                depth = len(current.parts) - root_parts

                if depth >= max_depth:
                    dirs[:] = []
                    continue

                # Ocultas/sistema y caches grandes no aportan valor como destino.
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                    and d.lower() not in {
                        "appdata", "node_modules", "__pycache__",
                        "$recycle.bin", "system volume information",
                    }
                ]

                for d in dirs:
                    path = current / d
                    self.add(d, path, source)

        except Exception as exc:
            print(f"[FOLDER DISCOVERY] {root}: {exc}")

    def build(self):
        self.index = {}

        user_profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
        one_drive = os.environ.get("OneDrive")

        common_roots = [
            (user_profile / "Desktop", "desktop"),
            (user_profile / "Documents", "documents"),
            (user_profile / "Downloads", "downloads"),
            (user_profile / "Pictures", "pictures"),
            (user_profile / "Videos", "videos"),
            (user_profile / "Music", "music"),
        ]

        if one_drive:
            common_roots.append((Path(one_drive), "onedrive"))

        # Directorios raíz con alias útiles.
        aliases = {
            "escritorio": user_profile / "Desktop",
            "desktop": user_profile / "Desktop",
            "documentos": user_profile / "Documents",
            "documents": user_profile / "Documents",
            "descargas": user_profile / "Downloads",
            "downloads": user_profile / "Downloads",
            "imagenes": user_profile / "Pictures",
            "imágenes": user_profile / "Pictures",
            "pictures": user_profile / "Pictures",
            "videos": user_profile / "Videos",
            "musica": user_profile / "Music",
            "música": user_profile / "Music",
            "music": user_profile / "Music",
        }

        for alias, path in aliases.items():
            self.add(alias, path, "known_folder")

        for path, source in common_roots:
            self._scan_root(path, source, max_depth=2)

        self.save()
        return self.index

    def save(self):
        try:
            with open(FOLDER_INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(self.index, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"[FOLDER DISCOVERY] No pude guardar índice: {exc}")

    def load_or_build(self):
        try:
            if os.path.exists(FOLDER_INDEX_FILE):
                with open(FOLDER_INDEX_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, dict) and data:
                    # Elimina entradas que ya no existen.
                    self.index = {
                        key: item
                        for key, item in data.items()
                        if os.path.isdir(item.get("path", ""))
                    }

                    if self.index:
                        return self.index
        except Exception:
            pass

        return self.build()

    def refresh(self):
        return self.build()

    def find(self, query):
        if not self.index:
            self.load_or_build()

        raw = (query or "").strip().strip('"').strip("'")

        # Si el usuario proporciona una ruta real, no hace falta buscar.
        expanded = os.path.expandvars(os.path.expanduser(raw))

        if os.path.isdir(expanded):
            return {
                "name": Path(expanded).name or expanded,
                "path": expanded,
                "source": "direct_path",
            }, 1.0

        q = normalizar_nombre_carpeta(raw)

        if not q:
            return None, 0.0

        if q in self.index:
            return self.index[q], 1.0

        best = None
        best_score = 0.0

        for key, item in self.index.items():
            if q in key or key in q:
                score = min(len(q), len(key)) / max(len(q), len(key))
                score = max(score, 0.88)
            else:
                score = difflib.SequenceMatcher(None, q, key).ratio()

            if score > best_score:
                best_score = score
                best = item

        if best_score >= 0.72:
            return best, best_score

        return None, best_score

    def launch(self, query):
        item, score = self.find(query)

        if not item:
            self.refresh()
            item, score = self.find(query)

        if not item:
            return False, None, score

        try:
            os.startfile(item["path"])
            return True, item, score
        except Exception as exc:
            print(f"[FOLDER LAUNCH] {item.get('path')}: {exc}")
            return False, item, score


folder_discovery = FolderDiscovery()
folder_discovery.load_or_build()



def normalizar(texto):
    return texto.lower().strip()


def buscar_en_carpetas(nombre_navegador):
    carpetas = [
        r"C:\Users\Gabo\AppData\Local\Programs",
        r"C:\Program Files",
        r"C:\Program Files (x86)",
    ]

    nombres_exe = ["launcher.exe", "opera.exe"]

    for carpeta in carpetas:
        if not os.path.exists(carpeta):
            continue

        for root, dirs, files in os.walk(carpeta):
            root_lower = root.lower()

            if nombre_navegador == "opera gx":
                if "opera gx" not in root_lower:
                    continue

            if nombre_navegador == "opera":
                if "opera" not in root_lower or "opera gx" in root_lower:
                    continue

            for exe in nombres_exe:
                posible = os.path.join(root, exe)

                if os.path.exists(posible):
                    return posible

    return None


def encontrar_path(paths, nombre_navegador=None):
    for path in paths:
        if os.path.exists(path):
            return path

    if nombre_navegador in ["opera", "opera gx"]:
        encontrado = buscar_en_carpetas(nombre_navegador)

        if encontrado:
            return encontrado

    return None


def abrir_navegador(nombre="chrome", url=None):
    paths = BROWSER_PATHS.get(nombre, BROWSER_PATHS["chrome"])
    exe = encontrar_path(paths, nombre_navegador=nombre)

    if not exe:
        return False

    if url:
        subprocess.Popen([exe, url])
    else:
        subprocess.Popen([exe])

    return True


def detectar_navegador(texto):
    t = normalizar(texto)

    if "opera gx" in t or "opera gaming" in t:
        return "opera gx"

    if "opera" in t:
        return "opera"

    if "chrome" in t or "google chrome" in t:
        return "chrome"

    return "chrome"


def abrir_app(nombre):
    """
    Primero intenta descubrimiento automático. Si no encuentra nada, conserva
    el comportamiento especial de navegadores del servidor original.
    """
    nombre = normalizar(nombre)

    if nombre in ["opera", "opera gx", "chrome", "google chrome"]:
        nav = detectar_navegador(nombre)

        if abrir_navegador(nav):
            return True, {
                "name": nav,
                "source": "browser_handler",
            }

    ok, item, score = app_discovery.launch(nombre)

    if ok:
        return True, item

    return False, None



def limpiar_texto_busqueda(texto):
    t = normalizar(texto)

    basura = [
        "en youtube",
        "por youtube",
        "en google",
        "en chrome",
        "en el chrome",
        "en opera gx",
        "en el opera gx",
        "en opera",
        "en el opera",
        "por google",
    ]

    for b in basura:
        t = t.replace(b, "")

    return t.strip()


def extraer_busqueda(texto):
    t = normalizar(texto)

    frases = [
        "busca videos de",
        "buscar videos de",
        "buscame videos de",
        "búscame videos de",
        "busca video de",
        "buscar video de",
        "busca",
        "buscar",
        "buscame",
        "búscame",
    ]

    for frase in frases:
        if frase in t:
            return limpiar_texto_busqueda(t.split(frase, 1)[1].strip())

    return ""


def extraer_cancion(texto):
    t = normalizar(texto)

    frases = [
        "reproduce",
        "ponme",
        "pon",
        "quiero escuchar",
        "escuchar",
        "toca",
    ]

    for frase in frases:
        if frase in t:
            return limpiar_texto_busqueda(t.split(frase, 1)[1].strip())

    return ""


def buscar_web(query, navegador="chrome", youtube=False):
    encoded = urllib.parse.quote(query)

    if youtube:
        url = f"https://www.youtube.com/results?search_query={encoded}"
    else:
        url = f"https://www.google.com/search?q={encoded}"

    return abrir_navegador(navegador, url)


def reproducir_youtube(query, navegador="chrome"):
    ydl_opts = {
        "quiet": True,
        "default_search": "ytsearch1",
        "skip_download": True,
        "format": "best",
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)

        if "entries" in info and info["entries"]:
            video = info["entries"][0]
            url = video.get("webpage_url")

            if url:
                return abrir_navegador(navegador, url)

    return False


def separar_ordenes(texto):
    t = f" {texto.lower().strip()} "

    reemplazos = {
        " ponme ": " pon ",
        " pones ": " pon ",
        " poneme ": " pon ",
        " abreme ": " abre ",
        " ábreme ": " abre ",
        " abri ": " abre ",
        " abrí ": " abre ",
    }

    for viejo, nuevo in reemplazos.items():
        t = t.replace(viejo, nuevo)

    t = t.strip()

    separadores = [
        " mientras ",
        " después ",
        " despues ",
        " luego ",
        " también ",
        " tambien ",
        " y ",
    ]

    ordenes = [t]

    for sep in separadores:
        nuevas = []

        for orden in ordenes:
            nuevas.extend(orden.split(sep))

        ordenes = nuevas

    return [o.strip() for o in ordenes if o.strip()]


def procesar_orden(orden, navegador_actual="chrome"):
    t = normalizar(orden)

    navegador = (
        detectar_navegador(t)
        if any(b in t for b in ["chrome", "opera", "opera gx", "opera gaming"])
        else navegador_actual
    )

    # Abrir navegador explícito
    abrir_navegadores = [
        "abre chrome",
        "abrir chrome",
        "abre google chrome",
        "abre opera",
        "abrir opera",
        "abre opera gx",
        "abrir opera gx",
        "abre opera gaming",
        "abrir opera gaming",
    ]

    if t in abrir_navegadores:
        ok = abrir_navegador(navegador)

        return {
            "handled": True,
            "respuesta": f"Abriendo {navegador}." if ok else f"No encontré {navegador}.",
            "navegador": navegador,
        }

    # Abrir navegador + búsqueda
    if (
        ("abre " in t or "abrir " in t)
        and ("chrome" in t or "opera" in t)
        and ("busca" in t or "buscar" in t or "buscame" in t or "búscame" in t)
    ):
        busqueda = extraer_busqueda(t)

        if busqueda:
            youtube = "video" in t or "videos" in t or "youtube" in t
            ok = buscar_web(busqueda, navegador=navegador, youtube=youtube)

            return {
                "handled": True,
                "respuesta": f"Buscando en {navegador}." if ok else f"No pude abrir {navegador}.",
                "navegador": navegador,
            }

    # Buscar videos
    if (
        "busca videos de" in t
        or "buscar videos de" in t
        or "buscame videos de" in t
        or "búscame videos de" in t
        or "busca video de" in t
        or "buscar video de" in t
    ):
        busqueda = extraer_busqueda(t)

        if busqueda:
            ok = buscar_web(busqueda, navegador=navegador, youtube=True)

            return {
                "handled": True,
                "respuesta": "Buscando videos." if ok else f"No pude abrir {navegador}.",
                "navegador": navegador,
            }

    # Buscar general
    if (
        t.startswith("busca ")
        or t.startswith("buscar ")
        or t.startswith("buscame ")
        or t.startswith("búscame ")
    ):
        busqueda = extraer_busqueda(t)

        if busqueda:
            ok = buscar_web(busqueda, navegador=navegador, youtube=False)

            return {
                "handled": True,
                "respuesta": f"Buscando en {navegador}." if ok else f"No pude abrir {navegador}.",
                "navegador": navegador,
            }

    # Reproducir música/video
    if (
        t.startswith("reproduce ")
        or t.startswith("pon ")
        or t.startswith("ponme ")
        or t.startswith("quiero escuchar ")
        or t.startswith("escuchar ")
        or t.startswith("toca ")
    ):
        cancion = extraer_cancion(t)

        if cancion:
            ok = reproducir_youtube(cancion, navegador=navegador)

            return {
                "handled": True,
                "respuesta": "Reproduciendo." if ok else "No pude reproducir eso.",
                "navegador": navegador,
            }

    # Abrir carpeta explícita
    folder_patterns = [
        r"^(?:abre|abrir|abri|abrí|ábreme|abreme)\s+(?:la\s+)?carpeta\s+(.+)$",
        r"^(?:abre|abrir|abri|abrí|ábreme|abreme)\s+(?:mis\s+|mi\s+)?(documentos|descargas|escritorio|imagenes|imágenes|videos|musica|música|downloads|documents|desktop|pictures|music)$",
    ]

    for pattern in folder_patterns:
        match = re.match(pattern, t, flags=re.IGNORECASE)

        if match:
            carpeta_nombre = match.group(1).strip()

            ok_folder, folder_item, folder_score = folder_discovery.launch(
                carpeta_nombre
            )

            if ok_folder:
                return {
                    "handled": True,
                    "respuesta": f"Abriendo {folder_item.get('name', carpeta_nombre)}.",
                    "navegador": navegador,
                }

            return {
                "handled": True,
                "respuesta": f"No encontré la carpeta {carpeta_nombre}.",
                "navegador": navegador,
            }

    # Abrir apps
    comandos_abrir = ["abre", "abrir", "abri", "abrí", "ábreme", "abreme"]

    for comando in comandos_abrir:
        if t.startswith(comando + " "):
            app_nombre = t.replace(comando, "", 1).strip()

            ok_app, app_detectada = abrir_app(app_nombre)

            if ok_app:
                nuevo_nav = detectar_navegador(app_nombre)

                nombre_mostrado = (
                    app_detectada.get("name")
                    if isinstance(app_detectada, dict)
                    else app_nombre
                )

                return {
                    "handled": True,
                    "respuesta": f"Abriendo {nombre_mostrado}.",
                    "navegador": nuevo_nav,
                }

            return {
                "handled": True,
                "respuesta": f"No encontré {app_nombre}.",
                "navegador": navegador,
            }

    return {
        "handled": False,
        "respuesta": "",
        "navegador": navegador_actual,
    }



@app.route("/apps", methods=["GET"])
def listar_apps_detectadas():
    return jsonify({
        "ok": True,
        "cantidad": len(app_discovery.index),
        "apps": sorted(
            [
                {
                    "name": item.get("name", key),
                    "source": item.get("source", ""),
                }
                for key, item in app_discovery.index.items()
            ],
            key=lambda x: x["name"].lower(),
        ),
    })


@app.route("/refresh_apps", methods=["POST"])
def refrescar_apps():
    index = app_discovery.refresh()

    return jsonify({
        "ok": True,
        "cantidad": len(index),
        "respuesta": f"Índice actualizado. Detecté {len(index)} aplicaciones.",
    })


@app.route("/find_app", methods=["POST"])
def find_app():
    data = request.get_json(silent=True) or {}
    nombre = (data.get("nombre") or "").strip()

    item, score = app_discovery.find(nombre)

    return jsonify({
        "ok": bool(item),
        "score": round(score, 3),
        "app": item,
    })



@app.route("/folders", methods=["GET"])
def listar_carpetas_detectadas():
    return jsonify({
        "ok": True,
        "cantidad": len(folder_discovery.index),
        "folders": sorted(
            [
                {
                    "name": item.get("name", key),
                    "path": item.get("path", ""),
                    "source": item.get("source", ""),
                }
                for key, item in folder_discovery.index.items()
            ],
            key=lambda x: x["name"].lower(),
        ),
    })


@app.route("/refresh_folders", methods=["POST"])
def refrescar_carpetas():
    index = folder_discovery.refresh()

    return jsonify({
        "ok": True,
        "cantidad": len(index),
        "respuesta": f"Índice de carpetas actualizado. Detecté {len(index)} carpetas.",
    })


@app.route("/find_folder", methods=["POST"])
def find_folder():
    data = request.get_json(silent=True) or {}
    nombre = (data.get("nombre") or "").strip()

    item, score = folder_discovery.find(nombre)

    return jsonify({
        "ok": bool(item),
        "score": round(score, 3),
        "folder": item,
    })


@app.route("/accion", methods=["POST"])
def accion():
    data = request.get_json()
    texto = data.get("texto", "").strip()

    if not texto:
        return jsonify({"handled": False})

    ordenes = separar_ordenes(texto)

    respuestas = []
    alguna_manejada = False
    navegador_actual = detectar_navegador(texto)

    for orden in ordenes:
        resultado = procesar_orden(orden, navegador_actual=navegador_actual)

        navegador_actual = resultado.get("navegador", navegador_actual)

        if resultado["handled"]:
            alguna_manejada = True
            respuesta = resultado.get("respuesta", "")

            if respuesta:
                respuestas.append(respuesta)

    if alguna_manejada:
        return jsonify({
            "handled": True,
            "respuesta": " ".join(respuestas).strip() or "Hecho.",
        })

    return jsonify({"handled": False})


if __name__ == "__main__":
    print("App Opener Server v3 iniciado en http://127.0.0.1:5050")
    print(f"Aplicaciones indexadas: {len(app_discovery.index)}")
    print(f"Carpetas indexadas: {len(folder_discovery.index)}")
    app.run(host="127.0.0.1", port=5050)
