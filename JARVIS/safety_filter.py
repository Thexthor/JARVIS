import re

PALABRAS_PELIGROSAS = [
    "matar",
    "asesinar",
    "suicid",
    "bomb",
    "terror",
    "hackear banco",
]

INSULTOS_COMUNES = [
    "idiota",
    "imbecil",
    "imbécil",
    "estupido",
    "estúpido",
    "tonto",
    "te la jeta",
    "mamaguevo",
    "cabron",
    "cabrón",
]

PREGUNTAS_SIGNIFICADO = [
    "que significa",
    "qué significa",
    "significado de",
    "que quiere decir",
    "qué quiere decir",
    "explica",
]


def normalizar(texto):
    texto = texto.lower()

    texto = re.sub(
        r"[^\wáéíóúñ ]",
        " ",
        texto
    )

    return texto.strip()


def contiene_peligro_real(texto):
    texto = normalizar(texto)

    for palabra in PALABRAS_PELIGROSAS:
        if palabra in texto:
            return True

    return False


def es_pregunta_significado(texto):
    texto = normalizar(texto)

    for patron in PREGUNTAS_SIGNIFICADO:
        if patron in texto:
            return True

    return False


def contiene_insulto(texto):
    texto = normalizar(texto)

    for insulto in INSULTOS_COMUNES:
        if insulto in texto:
            return True

    return False


def evaluar_mensaje(texto):
    texto_normalizado = normalizar(texto)

    # 🔥 Permitir preguntas de significado
    if es_pregunta_significado(texto_normalizado):
        return {
            "permitido": True,
            "razon": "pregunta_educativa"
        }

    # 🔥 Bloquear SOLO peligro real
    if contiene_peligro_real(texto_normalizado):
        return {
            "permitido": False,
            "razon": "contenido_peligroso"
        }

    # 🔥 Permitir modismos / slang / insultos coloquiales
    if contiene_insulto(texto_normalizado):
        return {
            "permitido": True,
            "razon": "modismo_o_contexto_social"
        }

    return {
        "permitido": True,
        "razon": "normal"
    }