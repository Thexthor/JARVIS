from flask import Flask, request, jsonify
from flask_cors import CORS

from datetime import datetime
from typing import List, Optional
import json
import os
import re
import threading

import requests


app = Flask(__name__)
CORS(app)

MEMORY_FILE = "jarvis_memory.json"
CONTEXT_FILE = "jarvis_context.json"

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "jarvis2"
OLLAMA_TIMEOUT = 7
OLLAMA_RUNNER_CTX = 2048

MAX_RECENT_TURNS = 10
MAX_CONTEXT_ENTITIES = 12

_file_lock = threading.Lock()


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalizar(texto: str) -> str:
    texto = (texto or "").lower()
    texto = re.sub(r"https?://\S+", " ", texto)
    texto = re.sub(r"[^a-záéíóúñ0-9 ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def cargar_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with _file_lock:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return default


def guardar_json(path: str, data):
    tmp = path + ".tmp"
    with _file_lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


# ============================================================
# MEMORIA PERMANENTE - mantiene endpoints existentes
# ============================================================

def cargar_memoria():
    data = cargar_json(MEMORY_FILE, [])
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("memoria"), list):
        return data["memoria"]
    return []


def guardar_memoria(memoria):
    guardar_json(MEMORY_FILE, memoria)


def limpiar_texto(texto):
    texto = (texto or "").strip()
    patrones = [
        r"^\s*jarvis[\s,;:.-]*recuerda que\s+",
        r"^\s*jarvis[\s,;:.-]*recuerda\s+",
        r"^\s*recuerda que\s+",
        r"^\s*recuerda\s+",
        r"^\s*guarda esto[\s,:-]*",
    ]
    for patron in patrones:
        texto = re.sub(patron, "", texto, flags=re.IGNORECASE)
    return texto.strip()


def detectar_dato(texto):
    original_limpio = limpiar_texto(texto)
    t = normalizar(original_limpio)

    patrones = [
        ("color_favorito", r"mi color favorito es (.+)", "Tu color favorito es {}."),
        ("novia", r"mi novia se llama (.+)", "Tu novia se llama {}."),
        ("novio", r"mi novio se llama (.+)", "Tu novio se llama {}."),
        ("nombre", r"me llamo (.+)", "Te llamas {}."),
        ("edad", r"tengo (.+) años", "Tienes {} años."),
        ("comida_favorita", r"mi comida favorita es (.+)", "Tu comida favorita es {}."),
        ("musica_favorita", r"mi música favorita es (.+)", "Tu música favorita es {}."),
        ("musica_favorita", r"mi musica favorita es (.+)", "Tu música favorita es {}."),
        ("juego_favorito", r"mi juego favorito es (.+)", "Tu juego favorito es {}."),
        ("me_gusta", r"me gusta (.+)", "Te gusta {}."),
        ("vivo_en", r"vivo en (.+)", "Vives en {}."),
        ("trabajo_en", r"trabajo en (.+)", "Trabajas en {}."),
        ("prefiero", r"prefiero (.+)", "Prefieres {}."),
    ]

    for clave, regex, respuesta in patrones:
        match = re.search(regex, t, flags=re.IGNORECASE)
        if match:
            valor = match.group(1).strip().rstrip(".")
            return {
                "tipo": "dato",
                "clave": clave,
                "valor": valor,
                "texto": respuesta.format(valor),
            }

    return {
        "tipo": "nota",
        "clave": "nota",
        "valor": original_limpio,
        "texto": original_limpio,
    }


def upsert_memoria(memoria: List[dict], nuevo: dict) -> List[dict]:
    clave = nuevo.get("clave")
    if clave and clave != "nota":
        memoria = [
            item for item in memoria
            if not (item.get("clave") == clave and item.get("tipo") == "dato")
        ]

    nuevo_norm = normalizar(nuevo.get("texto", ""))
    for item in memoria:
        if normalizar(item.get("texto", "")) == nuevo_norm:
            return memoria

    memoria.append(nuevo)
    return memoria


def buscar_respuesta(pregunta, memoria):
    p = normalizar(pregunta)
    claves = []

    reglas = [
        ("color_favorito", ["color favorito"]),
        ("novia", ["novia"]),
        ("novio", ["novio"]),
        ("nombre", ["como me llamo", "mi nombre"]),
        ("edad", ["edad", "cuantos años"]),
        ("comida_favorita", ["comida favorita"]),
        ("musica_favorita", ["musica favorita"]),
        ("juego_favorito", ["juego favorito"]),
        ("vivo_en", ["donde vivo"]),
        ("trabajo_en", ["donde trabajo"]),
        ("prefiero", ["que prefiero"]),
    ]

    for clave, frases in reglas:
        if any(normalizar(frase) in p for frase in frases):
            claves.append(clave)

    resultados = []
    for item in reversed(memoria):
        if item.get("clave") in claves:
            resultados.append({
                "texto": item.get("texto", item.get("valor", "")),
                "fecha": item.get("fecha", ""),
                "clave": item.get("clave", ""),
            })

    if resultados:
        return resultados[:5]

    palabras = [
        palabra for palabra in re.findall(r"[a-záéíóúñ0-9]+", p)
        if len(palabra) > 2
    ]
    scored = []
    for item in memoria:
        corpus = normalizar(
            f"{item.get('texto', '')} {item.get('valor', '')} {item.get('original', '')}"
        )
        score = sum(1 for palabra in palabras if palabra in corpus)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    for _, item in scored[:5]:
        resultados.append({
            "texto": item.get("texto", item.get("valor", "")),
            "fecha": item.get("fecha", ""),
            "clave": item.get("clave", ""),
        })
    return resultados


# ============================================================
# CONTEXTO CONVERSACIONAL
# ============================================================

def contexto_default():
    return {
        "tema_actual": "",
        "tipo_entidad": "",
        "entidades": [],
        "ultima_intencion": "",
        "ultima_relacion": "",
        "ultimo_vocativo": "",
        "ultimo_tono": "neutral",
        "turnos": [],
        "updated_at": "",
    }


def cargar_contexto():
    data = cargar_json(CONTEXT_FILE, contexto_default())
    if not isinstance(data, dict):
        return contexto_default()
    base = contexto_default()
    base.update(data)
    return base


def guardar_contexto(contexto):
    contexto["updated_at"] = now_str()
    contexto["turnos"] = contexto.get("turnos", [])[-MAX_RECENT_TURNS:]
    contexto["entidades"] = contexto.get("entidades", [])[-MAX_CONTEXT_ENTITIES:]
    guardar_json(CONTEXT_FILE, contexto)


def strip_jarvis_anchor(texto: str) -> str:
    return re.sub(
        r"^\s*(oye\s+|hey\s+)?jarvis\b[\s,;:.-]*",
        "",
        (texto or "").strip(),
        count=1,
        flags=re.IGNORECASE,
    ).strip()


def ollama_health() -> bool:
    try:
        return requests.get(
            "http://127.0.0.1:11434/api/tags",
            timeout=2,
        ).status_code == 200
    except Exception:
        return False


def call_ollama_json(prompt: str, num_predict: int = 650) -> Optional[dict]:
    if not ollama_health():
        return None

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "20m",
                "options": {
                    "temperature": 0.0,
                    "num_predict": num_predict,
                    "num_ctx": OLLAMA_RUNNER_CTX,
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )
        r.raise_for_status()
        raw = (r.json().get("response") or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
        return json.loads(raw)
    except Exception as exc:
        print("[CONTEXT OLLAMA]", exc)
        return None


def fallback_parse(pregunta: str, contexto: dict) -> dict:
    original = pregunta.strip()
    limpia = strip_jarvis_anchor(original)
    t = normalizar(limpia)

    reference_markers = [
        " y ", " el ", " la ", " lo ", " eso", " esa", " ese",
        "este", "esta", "su ", "sus ", "del libro", "de la pelicula",
        "de la película", "quien lo", "quién lo", "cuando sale",
        "cuándo sale", "cuando salio", "cuándo salió",
    ]

    usa_contexto = (
        len(t.split()) <= 10
        and any(marker.strip() in t for marker in reference_markers)
        and bool(contexto.get("tema_actual"))
    )

    pregunta_resuelta = limpia
    if usa_contexto:
        pregunta_resuelta = f"{limpia} Contexto: {contexto.get('tema_actual')}"

    return {
        "pregunta_original": original,
        "pregunta_limpia": limpia,
        "pregunta_resuelta": pregunta_resuelta,
        "vocativo": "",
        "tono": "neutral",
        "intencion": "",
        "relacion": "",
        "entidad_principal": contexto.get("tema_actual", "") if usa_contexto else "",
        "tipo_entidad": contexto.get("tipo_entidad", "") if usa_contexto else "",
        "entidades": contexto.get("entidades", []) if usa_contexto else [],
        "usa_contexto": usa_contexto,
        "confianza": 0.35,
    }



def fast_context_resolver(pregunta: str, contexto: dict) -> Optional[dict]:
    """
    Resolve common follow-ups without calling Ollama.

    Returns None only when the phrase is genuinely ambiguous enough to justify
    an LLM call. This keeps ordinary questions off the expensive context path.
    """
    original = (pregunta or "").strip()
    limpia = strip_jarvis_anchor(original)
    t = normalizar(limpia)
    tema = str(contexto.get("tema_actual") or "").strip()
    tipo = str(contexto.get("tipo_entidad") or "").strip()

    if not limpia:
        return None

    # Self-contained questions: never pay an LLM call merely to classify them.
    self_contained_starts = (
        "quien es ", "quién es ", "que es ", "qué es ",
        "de quien es ", "de quién es ", "quien dirige ", "quién dirige ",
        "quien escribio ", "quién escribió ", "quien escribió ",
        "quien creo ", "quién creó ", "quien creó ",
        "cuando salio ", "cuándo salió ", "cuando sale ", "cuándo sale ",
        "cuanto cuesta ", "cuánto cuesta ", "donde esta ", "dónde está ",
        "dime ", "busca ", "investiga ", "explica ", "explicame ",
        "explícame ", "compara ", "abre ", "inicia ", "ejecuta ",
        "lanza ", "reproduce ", "pon ",
    )

    if t.startswith(self_contained_starts) and len(t.split()) >= 3:
        return {
            "pregunta_original": original,
            "pregunta_limpia": limpia,
            "pregunta_resuelta": limpia,
            "vocativo": "",
            "tono": "neutral",
            "intencion": "",
            "relacion": "",
            "entidad_principal": "",
            "tipo_entidad": "",
            "entidades": [],
            "usa_contexto": False,
            "confianza": 0.95,
            "modo": "fast_direct",
        }

    # Clear follow-up patterns that can be resolved from the active topic.
    if tema:
        relation_patterns = [
            (r"^(?:y\s+)?(?:quien|quién)\s+(?:lo|la)\s+dirige\??$", "director",
             f"¿Quién dirige {tema}?"),
            (r"^(?:y\s+)?(?:quien|quién)\s+(?:lo|la)\s+escribio\??$", "autor",
             f"¿Quién escribió {tema}?"),
            (r"^(?:y\s+)?(?:quien|quién)\s+(?:lo|la)\s+creo\??$", "creador",
             f"¿Quién creó {tema}?"),
            (r"^(?:y\s+)?(?:cuando|cuándo)\s+(?:sale|salio|salió)\??$", "fecha",
             f"¿Cuándo salió o sale {tema}?"),
            (r"^(?:y\s+)?(?:cuanto|cuánto)\s+(?:cuesta|vale)\??$", "precio",
             f"¿Cuánto cuesta {tema}?"),
            (r"^(?:y\s+)?(?:donde|dónde)\s+(?:esta|está)\??$", "ubicacion",
             f"¿Dónde está {tema}?"),
            (r"^(?:y\s+)?(?:quien|quién)\s+es\s+(?:el|la)\s+autor(?:a)?\??$", "autor",
             f"¿Quién es el autor de {tema}?"),
        ]

        for pattern, relacion, resolved_query in relation_patterns:
            if re.match(pattern, t, flags=re.IGNORECASE):
                return {
                    "pregunta_original": original,
                    "pregunta_limpia": limpia,
                    "pregunta_resuelta": resolved_query,
                    "vocativo": "",
                    "tono": "neutral",
                    "intencion": "seguimiento",
                    "relacion": relacion,
                    "entidad_principal": tema,
                    "tipo_entidad": tipo,
                    "entidades": [tema],
                    "usa_contexto": True,
                    "confianza": 0.98,
                    "modo": "fast_context",
                }

    return None


def resolver_contexto(pregunta: str, contexto: dict, historial_cliente=None) -> dict:
    fast = fast_context_resolver(pregunta, contexto)

    if fast is not None:
        return fast

    historial_cliente = historial_cliente or []
    recent = contexto.get("turnos", [])[-6:]

    for turn in historial_cliente[-6:]:
        if not isinstance(turn, dict):
            continue
        user = turn.get("user", "")
        jarvis = turn.get("jarvis", "")
        if user or jarvis:
            recent.append({"usuario": user, "jarvis": jarvis})

    recent = recent[-8:]

    prompt = f"""
Eres el Semantic Context Resolver de JARVIS.

NO respondas al usuario. Analiza su mensaje y devuelve estructura JSON.

El usuario SIEMPRE se dirige al asistente con la palabra "Jarvis".
Después de "Jarvis" puede haber cualquier vocativo o apodo. Ese vocativo es
social, NO es parte del tema.

Resuelve de forma GENERAL:
- vocativo/apodo;
- pregunta real;
- intención;
- entidad o entidades;
- tipo de entidad si es claro;
- relación solicitada: autor, director, fecha, precio, creador, ubicación,
  protagonista, definición, comparación, noticias, etc.;
- referencias al contexto anterior.

No sustituyas una relación por otra. Si preguntan quién dirige una película,
la relación es director, no protagonista. Si preguntan "de quién es un libro",
la relación es autoría. Si dicen "¿y cuándo sale?", hereda la entidad anterior.

La pregunta_resuelta debe ser autosuficiente, mantener la intención exacta y
añadir solo el contexto necesario.

REGLA CRÍTICA PARA ACCIONES:
- Si el usuario da una orden ejecutable (abrir, cerrar, iniciar, ejecutar,
  lanzar, reproducir, buscar, etc.), NO la conviertas en una frase descriptiva.
- Conserva el verbo imperativo en pregunta_limpia y pregunta_resuelta.
- Ejemplo: "Jarvis abre OBS" -> "abre OBS", NUNCA "OBS se está abriendo".
- En esos casos usa intencion="accion" y, si aplica, relacion="abrir_app".

ESTADO:
{json.dumps({
    "tema_actual": contexto.get("tema_actual", ""),
    "tipo_entidad": contexto.get("tipo_entidad", ""),
    "entidades": contexto.get("entidades", []),
    "ultima_intencion": contexto.get("ultima_intencion", ""),
    "ultima_relacion": contexto.get("ultima_relacion", ""),
}, ensure_ascii=False)}

TURNOS:
{json.dumps(recent, ensure_ascii=False)}

MENSAJE:
{pregunta}

Devuelve SOLO JSON válido:
{{
  "pregunta_original": "...",
  "pregunta_limpia": "...",
  "pregunta_resuelta": "...",
  "vocativo": "",
  "tono": "neutral|cariñoso|burlón|frustrado|emocionado|formal|informal",
  "intencion": "...",
  "relacion": "...",
  "entidad_principal": "",
  "tipo_entidad": "",
  "entidades": [],
  "usa_contexto": true,
  "confianza": 0.0
}}
"""

    parsed = call_ollama_json(prompt, num_predict=320) or fallback_parse(pregunta, contexto)

    parsed["pregunta_original"] = pregunta
    parsed["pregunta_limpia"] = str(
        parsed.get("pregunta_limpia") or strip_jarvis_anchor(pregunta)
    ).strip()
    parsed["pregunta_resuelta"] = str(
        parsed.get("pregunta_resuelta") or parsed["pregunta_limpia"]
    ).strip()
    parsed["vocativo"] = str(parsed.get("vocativo") or "").strip()
    parsed["tono"] = str(parsed.get("tono") or "neutral").strip()
    parsed["intencion"] = str(parsed.get("intencion") or "").strip()
    parsed["relacion"] = str(parsed.get("relacion") or "").strip()
    parsed["entidad_principal"] = str(parsed.get("entidad_principal") or "").strip()
    parsed["tipo_entidad"] = str(parsed.get("tipo_entidad") or "").strip()

    entidades = parsed.get("entidades", [])
    if not isinstance(entidades, list):
        entidades = []
    parsed["entidades"] = [str(x).strip() for x in entidades if str(x).strip()][:8]
    parsed["usa_contexto"] = bool(parsed.get("usa_contexto", False))

    try:
        parsed["confianza"] = float(parsed.get("confianza", 0.0))
    except Exception:
        parsed["confianza"] = 0.0

    return parsed


def aplicar_resolucion_al_contexto(contexto: dict, resolved: dict):
    entidad = resolved.get("entidad_principal", "").strip()
    if entidad:
        contexto["tema_actual"] = entidad

    tipo = resolved.get("tipo_entidad", "").strip()
    if tipo:
        contexto["tipo_entidad"] = tipo

    entidades = list(contexto.get("entidades", []))
    for item in resolved.get("entidades", []):
        if item and item not in entidades:
            entidades.append(item)
    if entidad and entidad not in entidades:
        entidades.append(entidad)

    contexto["entidades"] = entidades[-MAX_CONTEXT_ENTITIES:]

    if resolved.get("intencion"):
        contexto["ultima_intencion"] = resolved["intencion"]
    if resolved.get("relacion"):
        contexto["ultima_relacion"] = resolved["relacion"]
    if resolved.get("vocativo"):
        contexto["ultimo_vocativo"] = resolved["vocativo"]
    if resolved.get("tono"):
        contexto["ultimo_tono"] = resolved["tono"]

    return contexto


@app.route("/remember", methods=["POST"])
def remember():
    data = request.get_json(silent=True) or {}
    texto = data.get("texto", "").strip()

    if not texto:
        return jsonify({"ok": False, "respuesta": "No recibí nada para recordar."})

    memoria = cargar_memoria()
    dato = detectar_dato(texto)

    nuevo = {
        "tipo": dato["tipo"],
        "clave": dato["clave"],
        "valor": dato["valor"],
        "texto": dato["texto"],
        "original": texto,
        "fecha": now_str(),
    }

    memoria = upsert_memoria(memoria, nuevo)
    guardar_memoria(memoria)

    return jsonify({
        "ok": True,
        "respuesta": f"Listo, lo recordaré: {dato['texto']}",
    })


@app.route("/memory", methods=["GET"])
def memory():
    return jsonify({"memoria": cargar_memoria()})


@app.route("/search_memory", methods=["POST"])
def search_memory():
    data = request.get_json(silent=True) or {}
    pregunta = data.get("pregunta", "").strip()
    return jsonify({"resultados": buscar_respuesta(pregunta, cargar_memoria())})


@app.route("/clear_memory", methods=["POST"])
def clear_memory():
    guardar_memoria([])
    return jsonify({"ok": True, "respuesta": "Memoria borrada."})


@app.route("/resolve_context", methods=["POST"])
def resolve_context():
    data = request.get_json(silent=True) or {}
    pregunta = str(data.get("pregunta") or "").strip()
    historial = data.get("historial") or []

    if not pregunta:
        return jsonify({
            "ok": False,
            "pregunta_resuelta": "",
            "error": "Pregunta vacía.",
        }), 400

    contexto = cargar_contexto()
    resolved = resolver_contexto(pregunta, contexto, historial)
    contexto = aplicar_resolucion_al_contexto(contexto, resolved)
    guardar_contexto(contexto)

    return jsonify({"ok": True, **resolved})


@app.route("/commit_turn", methods=["POST"])
def commit_turn():
    data = request.get_json(silent=True) or {}
    usuario = str(data.get("usuario") or "").strip()
    jarvis = str(data.get("jarvis") or "").strip()
    resolved = data.get("resolved") or {}

    contexto = cargar_contexto()

    if isinstance(resolved, dict):
        contexto = aplicar_resolucion_al_contexto(contexto, resolved)

    if usuario or jarvis:
        contexto.setdefault("turnos", []).append({
            "usuario": usuario,
            "jarvis": jarvis,
            "pregunta_resuelta": resolved.get("pregunta_resuelta", "")
            if isinstance(resolved, dict) else "",
            "entidad": resolved.get("entidad_principal", "")
            if isinstance(resolved, dict) else "",
            "intencion": resolved.get("intencion", "")
            if isinstance(resolved, dict) else "",
            "relacion": resolved.get("relacion", "")
            if isinstance(resolved, dict) else "",
            "fecha": now_str(),
        })

    guardar_contexto(contexto)
    return jsonify({"ok": True, "contexto": contexto})


@app.route("/context", methods=["GET"])
def get_context():
    return jsonify(cargar_contexto())


@app.route("/clear_context", methods=["POST"])
def clear_context():
    guardar_contexto(contexto_default())
    return jsonify({"ok": True, "respuesta": "Contexto conversacional borrado."})


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "ok": True,
        "memory": True,
        "context": True,
        "ollama": ollama_health(),
        "model": OLLAMA_MODEL,
        "version": "2.0",
    })


if __name__ == "__main__":
    print("")
    print("====================================================")
    print("       JARVIS MEMORY + CONTEXT ENGINE v2.0")
    print("====================================================")
    print("API       : http://127.0.0.1:5070")
    print("Memoria   : permanente + deduplicación")
    print("Contexto  : entidades + intención + referencias")
    print("Vocativos : dinámicos, anclados por 'Jarvis'")
    print("Resolver  : híbrido local/Ollama")
    print("====================================================")
    print("")
    app.run(host="127.0.0.1", port=5070, debug=False, threaded=True)
