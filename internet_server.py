from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from html.parser import HTMLParser
from typing import List, Optional, Tuple, Dict
import json
import re
import time
import traceback
import threading
from urllib.parse import urlparse

import requests


app = Flask(__name__)
CORS(app)


# ============================================================
# JARVIS INTERNET ENGINE v7.4
#
# Arquitectura:
#   IntentParser
#      ↓
#   SearXNG discovery
#      ↓
#   SearchResult quality/ranking
#      ↓
#   ArticleExtractor
#      ↓
#   ArticleCleaner + paragraph scoring
#      ↓
#   EvidenceBuilder + event ranking
#      ↓
#   Ollama (solo análisis complejo)
#      ↓
#   ResponseBuilder
#
# Principio central:
# SearXNG descubre URLs. Los snippets NO son la evidencia final.
# Jarvis abre artículos reales y extrae el núcleo informativo.
# ============================================================


# ============================================================
# CONFIG
# ============================================================

SEARXNG_URL = "http://127.0.0.1:8888/search"
SEARXNG_HOME = "http://127.0.0.1:8888"

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
OLLAMA_MODEL = "jarvis2"

DEFAULT_COUNT = 3
MAX_COUNT = 25

SEARCH_TIMEOUT = 20
ARTICLE_TIMEOUT = 12
OLLAMA_TIMEOUT = 120
OLLAMA_HEALTH_TIMEOUT = 3

RAW_RESULTS_PER_QUERY = 35
MAX_RANKED_RESULTS = 30
MAX_ARTICLES_TO_FETCH = 16
MAX_ARTICLE_TEXT = 16000
MAX_PARAGRAPHS_PER_ARTICLE = 35
NEWS_FRESH_DAYS = 30
NEWS_FALLBACK_DAYS = 60
STRICT_NEWS_FRESHNESS = True
ARTICLE_FETCH_WORKERS = 8
MIN_CONTEXT_SENTENCES = 2
MAX_CONTEXT_SENTENCES = 3

# One fixed runner configuration for jarvis2.
# Changing num_ctx between requests forces Ollama to rebuild/reload the runner.
OLLAMA_RUNNER_CTX = 2048


# ============================================================
# OLLAMA WARMUP
# ============================================================

def warm_ollama_model():
    """
    Carga jarvis2 al arrancar el Internet Server y lo mantiene residente.
    Se ejecuta en segundo plano para no bloquear Flask.
    """
    try:
        started = time.time()

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": "Responde únicamente: listo",
                "stream": False,
                "keep_alive": -1,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 4,
                    "num_ctx": OLLAMA_RUNNER_CTX,
                },
            },
            timeout=120,
        )

        response.raise_for_status()
        elapsed = int((time.time() - started) * 1000)

        print(
            f"[OLLAMA WARMUP] {OLLAMA_MODEL} cargado y residente "
            f"en {elapsed}ms"
        )

    except Exception as exc:
        print(f"[OLLAMA WARMUP] No pude precargar el modelo: {exc}")


def start_ollama_warmup():
    warm_ollama_model()




SOCIAL_DOMAINS = {
    "tiktok.com",
    "instagram.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "youtu.be",
    "threads.net",
    "pinterest.com",
}

LOW_VALUE_URL_MARKERS = {
    "/tag/",
    "/tags/",
    "/topic/",
    "/topics/",
    "/quote/",
    "/quotes/",
    "/stocks/",
    "/stock/",
    "/equities/",
    "/markets/",
    "/market/",
    "/cotizacion",
    "/foro",
    "/forum",
    "/category/",
    "/author/",
}

GENERIC_PATTERNS = [
    "todas las noticias",
    "consulta todas las noticias",
    "archivo de noticias",
    "última hora sobre",
    "ultima hora sobre",
    "últimas noticias sobre",
    "ultimas noticias sobre",
    "información, novedades",
    "informacion, novedades",
    "artículos, videos, fotos",
    "articulos, videos, fotos",
    "el más completo archivo",
    "el mas completo archivo",
    "todo sobre",
    "últimas noticias y actualidad",
    "ultimas noticias y actualidad",
    "latest news and updates",
    "breaking news and updates",
    "cotización",
    "cotizacion",
    "datos históricos",
    "datos historicos",
]

BOILERPLATE_PATTERNS = [
    "inicio",
    "menú",
    "menu",
    "newsletter",
    "boletín",
    "boletin",
    "suscríbete",
    "suscribete",
    "síguenos",
    "siguenos",
    "facebook",
    "twitter",
    "linkedin",
    "telegram",
    "whatsapp",
    "compartir",
    "share",
    "cookies",
    "política de privacidad",
    "politica de privacidad",
    "publicidad",
    "advertisement",
    "related stories",
    "related articles",
    "artículos relacionados",
    "articulos relacionados",
    "más noticias",
    "mas noticias",
    "leer también",
    "leer tambien",
    "comentarios",
]

TRUNCATED_ENDINGS = {
    "en una", "en un", "de una", "de un", "para una", "para un",
    "y una", "y un", "con una", "con un", "hasta el", "hasta la",
    "the", "a", "an", "to", "for", "with", "and", "of", "in",
}

UNCERTAINTY_MARKERS = [
    "habría", "habria", "podría", "podria", "según", "segun",
    "presuntamente", "aparentemente", "se cree",
    "reportedly", "could", "may", "might", "according to",
]

STOPWORDS = {
    "jarvis", "busca", "buscar", "internet", "google", "investiga",
    "investigar", "dime", "dimelas", "dímelas", "sobre", "las", "los",
    "una", "uno", "unos", "unas", "del", "por", "para", "con", "que",
    "qué", "como", "cómo", "más", "mas", "últimas", "ultimas",
    "últimos", "ultimos", "noticias", "noticia", "nuevas", "nueva",
    "nuevos", "nuevo", "hoy", "actual", "actuales", "reciente",
    "recientes", "de", "el", "la", "y", "o", "en", "a", "me",
    "explica", "explicame", "explícame", "analiza", "resume", "resumen",
    "importante", "importantes", "porque", "porqué",
}

COMPLEX_PATTERNS = [
    "explica", "explícame", "explicame", "analiza", "compara",
    "comparación", "comparacion", "detalles", "profundiza",
    "por qué", "porque", "importante", "importantes",
    "impacto", "consecuencias", "qué significa", "que significa",
]

NEWS_PATTERNS = [
    "noticia", "noticias", "últimas", "ultimas", "último", "ultimo",
    "nuevas", "nueva", "reciente", "recientes", "actualidad",
    "hoy", "esta semana",
]


# ============================================================
# MODELS
# ============================================================

@dataclass
class QueryIntent:
    original: str
    cleaned: str
    topic: str
    topic_tokens: List[str]
    count: int
    is_news: bool
    is_complex: bool

    goal: str = "inform"
    relation: str = ""
    temporal_focus: str = "any"
    diversity: str = "low"
    depth: int = 1
    unit_type: str = "fact"
    novelty: str = "normal"
    explicit_count: bool = False
    requires_web: bool = True


@dataclass
class SearchResult:
    title: str
    url: str
    content: str
    engine: str = ""
    published_date: str = ""
    query_used: str = ""
    language: str = ""
    score: float = 0.0

    @property
    def domain(self) -> str:
        try:
            return urlparse(self.url).netloc.lower().replace("www.", "")
        except Exception:
            return ""


@dataclass
class Article:
    title: str
    url: str
    domain: str
    paragraphs: List[str]
    published_date: str
    score: float


@dataclass
class Evidence:
    statement: str
    context: str
    title: str
    url: str
    domain: str
    published_date: str
    score: float
    uncertain: bool


# ============================================================
# TEXT UTILITIES
# ============================================================

def normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^a-záéíóúñ0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean(text: str, max_len: int = 1200) -> str:
    if not text:
        return ""

    text = unescape(str(text))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\.{2,}", ". ", text)
    text = text.strip(" .,-–—:")

    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "..."

    return text


def tokens(text: str) -> List[str]:
    parts = re.findall(r"[a-záéíóúñ0-9]+", normalize(text))
    return [x for x in parts if len(x) >= 3 and x not in STOPWORDS]


def similarity(a: str, b: str) -> float:
    sa = set(tokens(a))
    sb = set(tokens(b))

    if not sa or not sb:
        return 0.0

    return len(sa & sb) / len(sa | sb)


def is_generic(text: str) -> bool:
    n = normalize(text)
    return any(normalize(p) in n for p in GENERIC_PATTERNS)


def boilerplate_score(text: str) -> int:
    n = normalize(text)
    return sum(1 for pattern in BOILERPLATE_PATTERNS if normalize(pattern) in n)


def looks_truncated(text: str) -> bool:
    t = clean(text).lower()

    if not t:
        return True

    if t.endswith((":", ",", ";", "…", "...")):
        return True

    return any(t.endswith(" " + ending) or t == ending for ending in TRUNCATED_ENDINGS)


def has_uncertainty(text: str) -> bool:
    n = normalize(text)
    return any(normalize(marker) in n for marker in UNCERTAINTY_MARKERS)


def looks_english(text: str) -> bool:
    """
    Conservative language gate. If a block is clearly English, it is never
    shown raw to the user. Mixed blocks also count as English when English
    dominates.
    """
    words = re.findall(r"[a-záéíóúñ]+", (text or "").lower())

    if len(words) < 6:
        return False

    english_markers = {
        "the", "and", "with", "from", "this", "that", "will", "has", "have",
        "into", "more", "latest", "news", "movie", "movies", "series",
        "project", "projects", "reportedly", "announced", "getting", "ready",
        "history", "signed", "studio", "studios", "following", "months",
        "secrecy", "finally", "unveiled", "look", "character", "fans",
        "waiting", "official", "trailer", "photos", "show", "cast", "member",
        "before", "role", "after", "new", "best", "yet", "still", "when",
    }

    spanish_markers = {
        "el", "la", "los", "las", "de", "del", "que", "con", "para", "una",
        "un", "por", "como", "más", "esta", "este", "se", "ha", "han", "será",
        "fue", "son", "sobre", "desde", "tras", "durante", "también", "pero",
        "cuando", "donde", "según", "nuevo", "nueva", "anunció", "presentó",
    }

    english_hits = sum(1 for w in words if w in english_markers)
    spanish_hits = sum(1 for w in words if w in spanish_markers)

    # Either clearly English by ratio, or enough strong English markers.
    return (
        english_hits >= 5 and english_hits > spanish_hits
    ) or (
        english_hits >= 8 and english_hits >= spanish_hits
    )


def sentence_is_complete(text: str) -> bool:
    """
    A sentence is considered safe for user-facing output only if it is
    genuinely complete. Long fragments without terminal punctuation are
    rejected instead of being guessed as complete.
    """
    text = (text or "").strip()

    if len(text) < 55 or len(text.split()) < 9:
        return False

    if looks_truncated(text):
        return False

    return text.endswith((".", "!", "?", "”", '"', "’"))


def split_sentences(text: str) -> List[str]:
    """
    Split prose into complete sentences only.
    It also repairs a common crawler case where line breaks separate a
    sentence before punctuation by joining adjacent fragments conservatively.
    """
    text = clean(text, 12000)

    if not text:
        return []

    # Normalize hard line breaks that often split article prose.
    text = re.sub(r"\s*\n+\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # First pass: punctuation-aware extraction.
    raw_parts = re.split(r"(?<=[.!?])\s+", text)

    # Repair parts that are still incomplete by joining with following text.
    repaired = []
    buffer = ""

    for part in raw_parts:
        part = part.strip(" .,-–—:")

        if not part:
            continue

        candidate = f"{buffer} {part}".strip() if buffer else part

        if candidate.endswith((".", "!", "?")):
            repaired.append(candidate)
            buffer = ""
        else:
            buffer = candidate

    # Never emit leftover buffer without terminal punctuation.
    out = []

    for sentence in repaired:
        sentence = clean(sentence, 1800)

        if len(sentence) < 55:
            continue

        if len(sentence.split()) < 9:
            continue

        if is_generic(sentence):
            continue

        if boilerplate_score(sentence) >= 2:
            continue

        if not sentence_is_complete(sentence):
            continue

        promotional = normalize(sentence)

        if any(marker in promotional for marker in [
            "marvel unlimited", "instant access", "exclusive deals",
            "member only", "member-only", "suscribete", "suscríbete",
            "subscribe now",
        ]):
            continue

        out.append(sentence)

    return out



# ============================================================
# DATE / FRESHNESS
# ============================================================

def parse_publication_date(value: str) -> Optional[datetime]:
    """
    Parse common dates returned by SearXNG / JSON-LD / meta tags.
    Unknown formats return None instead of guessing.
    """
    if not value:
        return None

    raw = str(value).strip()

    # ISO 8601
    try:
        normalized = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # Common explicit formats
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %B %Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue

    return None


def age_days(value: str) -> Optional[float]:
    dt = parse_publication_date(value)

    if not dt:
        return None

    now = datetime.now(timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 86400.0)


def freshness_bucket(value: str) -> int:
    """
    0 = fresh (<=30d)
    1 = acceptable fallback (<=60d)
    2 = old/unknown
    """
    age = age_days(value)

    if age is None:
        return 2

    if age <= NEWS_FRESH_DAYS:
        return 0

    if age <= NEWS_FALLBACK_DAYS:
        return 1

    return 2




# ============================================================
# FRESHNESS CONFIDENCE
# ============================================================

SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

ENGLISH_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def date_from_url(url: str) -> Optional[datetime]:
    """
    Extract common /YYYY/MM/DD/, /YYYY-MM-DD/ and /YYYY/MM/ date patterns.
    This is evidence, not a guarantee, so callers score it rather than trust it
    blindly.
    """
    if not url:
        return None

    patterns = [
        r"/(20\d{2})[/-](0?[1-9]|1[0-2])[/-](0?[1-9]|[12]\d|3[01])(?:/|-)",
        r"/(20\d{2})[/-](0?[1-9]|1[0-2])(?:/|-)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)

        if not match:
            continue

        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3)) if match.lastindex and match.lastindex >= 3 else 1
            return datetime(year, month, day, tzinfo=timezone.utc)
        except Exception:
            continue

    return None


def relative_age_from_text(text: str) -> Optional[float]:
    """
    Return approximate age in days for phrases like:
    hace 2 días / 5 hours ago / ayer / today.
    """
    t = normalize(text)

    if re.search(r"\b(hoy|today)\b", t):
        return 0.0

    if re.search(r"\b(ayer|yesterday)\b", t):
        return 1.0

    patterns = [
        (r"hace\s+(\d+)\s+minuto", 1 / 1440),
        (r"hace\s+(\d+)\s+hora", 1 / 24),
        (r"hace\s+(\d+)\s+d[ií]a", 1),
        (r"hace\s+(\d+)\s+semana", 7),
        (r"(\d+)\s+minutes?\s+ago", 1 / 1440),
        (r"(\d+)\s+hours?\s+ago", 1 / 24),
        (r"(\d+)\s+days?\s+ago", 1),
        (r"(\d+)\s+weeks?\s+ago", 7),
    ]

    for pattern, multiplier in patterns:
        m = re.search(pattern, t)

        if m:
            return int(m.group(1)) * multiplier

    return None


def explicit_month_year_from_text(text: str) -> Optional[datetime]:
    t = normalize(text)
    current_year = datetime.now(timezone.utc).year

    for name, month in {**SPANISH_MONTHS, **ENGLISH_MONTHS}.items():
        m = re.search(rf"\b{name}\s+(20\d{{2}})\b", t)

        if m:
            try:
                return datetime(int(m.group(1)), month, 1, tzinfo=timezone.utc)
            except Exception:
                pass

        # Current-year month mention, useful for fresh-news searches.
        if re.search(rf"\b{name}\b", t):
            try:
                return datetime(current_year, month, 1, tzinfo=timezone.utc)
            except Exception:
                pass

    return None


def freshness_confidence(
    published_date: str,
    url: str = "",
    title: str = "",
    content: str = "",
) -> Tuple[float, Optional[float], str]:
    """
    Returns:
      confidence 0..1,
      estimated age in days (if known),
      reason.

    The point is to avoid the v4.7 failure mode where a perfectly fresh article
    with no parseable meta date was discarded outright.
    """
    now = datetime.now(timezone.utc)

    # 1. Explicit article/search metadata date: strongest signal.
    dt = parse_publication_date(published_date)

    if dt:
        age = max(0.0, (now - dt).total_seconds() / 86400.0)

        if age <= NEWS_FRESH_DAYS:
            return 1.0, age, "explicit_date"

        if age <= NEWS_FALLBACK_DAYS:
            return 0.55, age, "explicit_date_fallback"

        return 0.05, age, "explicit_date_old"

    # 2. Relative date language in result title/snippet.
    relative_age = relative_age_from_text(f"{title} {content}")

    if relative_age is not None:
        if relative_age <= NEWS_FRESH_DAYS:
            return 0.90, relative_age, "relative_text"

        if relative_age <= NEWS_FALLBACK_DAYS:
            return 0.50, relative_age, "relative_text_fallback"

        return 0.05, relative_age, "relative_text_old"

    # 3. Date encoded in URL.
    url_dt = date_from_url(url)

    if url_dt:
        age = max(0.0, (now - url_dt).total_seconds() / 86400.0)

        if age <= NEWS_FRESH_DAYS + 1:
            return 0.82, age, "url_date"

        if age <= NEWS_FALLBACK_DAYS + 1:
            return 0.45, age, "url_date_fallback"

        return 0.05, age, "url_date_old"

    # 4. Month/year text is weaker but useful.
    month_dt = explicit_month_year_from_text(f"{title} {content}")

    if month_dt:
        age = max(0.0, (now - month_dt).total_seconds() / 86400.0)

        if age <= 40:
            return 0.65, age, "month_text"

    return 0.0, None, "unknown"


def result_fresh_enough(result, strict: bool = True) -> bool:
    confidence, age, _ = freshness_confidence(
        result.published_date,
        result.url,
        result.title,
        result.content,
    )

    if strict:
        return confidence >= 0.60 and (age is None or age <= NEWS_FRESH_DAYS + 2)

    return confidence >= 0.40


def article_fresh_enough(article, strict: bool = True) -> bool:
    # Real extracted article date is strongest, but title/URL can still rescue
    # pages whose metadata omits datePublished.
    confidence, age, _ = freshness_confidence(
        article.published_date,
        article.url,
        article.title,
        " ".join(article.paragraphs[:2]),
    )

    if strict:
        return confidence >= 0.60 and (age is None or age <= NEWS_FRESH_DAYS + 2)

    return confidence >= 0.40


# ============================================================
# FACT SUPPORT VALIDATION
# ============================================================

def extract_numbers(text: str) -> set:
    return set(re.findall(r"\b\d+(?:[.,]\d+)?\b", text or ""))


def extract_years(text: str) -> set:
    return set(re.findall(r"\b20\d{2}\b", text or ""))


def extract_named_tokens(text: str) -> set:
    """
    High-risk proper-name detector used only as a hallucination guard.
    Unlike the older version, it avoids treating every sentence-initial
    capitalized word as a new entity.
    """
    if not text:
        return set()

    entities = set()

    # Quoted titles / project names.
    for value in re.findall(r'["“”\']([^"“”\']{2,90})["“”\']', text):
        entities.add(normalize(value))

    # Acronyms / all-caps tokens such as MCU, X-MEN, RDJ.
    for value in re.findall(r"\b[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9-]{1,}\b", text):
        entities.add(normalize(value))

    # Multi-word proper names: Kevin Feige, Midnight X-Men, San Diego.
    for value in re.findall(
        r"\b(?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:[-'][A-ZÁÉÍÓÚÑ]?[a-záéíóúñ]+)?"
        r"(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:[-'][A-ZÁÉÍÓÚÑ]?[a-záéíóúñ]+)?)+)\b",
        text,
    ):
        entities.add(normalize(value))

    return {e for e in entities if e}


def normalized_contains(haystack: str, needle: str) -> bool:
    return normalize(needle) in normalize(haystack)


def exact_supports_valid(supports, evidence_text: str) -> bool:
    """
    Accept literal support after normalization, plus near-literal support when
    punctuation/quotes changed slightly. The content still has to be grounded
    in the evidence.
    """
    if not isinstance(supports, list) or not supports:
        return False

    evidence_norm = normalize(evidence_text)
    evidence_tokens = set(tokens(evidence_text))
    valid = 0

    for support in supports[:5]:
        support = clean(str(support or ""), 500)

        if len(support) < 12:
            continue

        support_norm = normalize(support)

        if support_norm and support_norm in evidence_norm:
            valid += 1
            continue

        support_tokens = set(tokens(support))

        if len(support_tokens) >= 4:
            coverage = len(support_tokens & evidence_tokens) / max(1, len(support_tokens))

            if coverage >= 0.85:
                valid += 1

    return valid >= 1


def output_supported_by_evidence(
    summary: str,
    evidence_text: str,
    topic: str,
    supports=None,
) -> bool:
    """
    Grounding validator.

    Hard facts (numbers, years and proper-name/project entities) must exist in
    the evidence. Natural Spanish paraphrasing is allowed, so we no longer
    reject a good answer simply because its wording differs from the source.
    """
    if not summary or not evidence_text:
        return False

    if supports is not None and not exact_supports_valid(supports, evidence_text):
        print("[VALIDATOR] Ningún apoyo coincide suficientemente con la evidencia.")
        return False

    # Numbers / years can never appear from nowhere.
    if not extract_numbers(summary).issubset(extract_numbers(evidence_text)):
        print("[VALIDATOR] El resumen agregó una cifra no presente en la evidencia.")
        return False

    if not extract_years(summary).issubset(extract_years(evidence_text)):
        print("[VALIDATOR] El resumen agregó un año no presente en la evidencia.")
        return False

    # Proper names and quoted project titles are high-risk facts.
    evidence_entities = extract_named_tokens(evidence_text)
    summary_entities = extract_named_tokens(summary)

    unsupported_entities = {
        entity
        for entity in summary_entities
        if entity not in evidence_entities
        and not normalized_contains(evidence_text, entity)
        and not normalized_contains(topic, entity)
    }

    if unsupported_entities:
        print(
            "[VALIDATOR] Entidades no respaldadas:",
            ", ".join(sorted(unsupported_entities)),
        )
        return False

    # Topic relevance.
    topic_tokens = set(tokens(topic))
    summary_tokens = set(tokens(summary))
    evidence_tokens = set(tokens(evidence_text))

    if topic_tokens and not (
        topic_tokens & summary_tokens
        or topic_tokens & evidence_tokens
    ):
        return False

    if looks_english(summary):
        return False

    if looks_truncated(summary):
        return False

    # Need actual lexical grounding, but paraphrases do not need word-for-word
    # identity.
    overlap = summary_tokens & evidence_tokens

    if len(overlap) < 3:
        return False

    return True


# ============================================================
# INTENT
# ============================================================

class IntentParser:
    def parse(self, question: str) -> QueryIntent:
        original = (question or "").strip()

        cleaned = re.sub(
            r"^(jarvis[\s,]*)?"
            r"(busca en internet|busca en google|busca|investiga|investigar)"
            r"[\s,:-]+",
            "",
            original,
            flags=re.IGNORECASE,
        ).strip()

        low = normalize(cleaned)

        explicit_count = False
        count = 1
        m = re.search(r"\b(\d{1,2})\b", cleaned)

        if m:
            explicit_count = True
            count = max(1, min(int(m.group(1)), MAX_COUNT))
        elif any(x in low for x in [
            "noticias", "novedades", "cosas", "datos", "hechos",
            "actualizaciones", "anuncios",
        ]):
            count = DEFAULT_COUNT

        relation = ""
        goal = "inform"

        relation_map = [
            ("identity", "identify", [r"\bquien es\b", r"\bquién es\b"]),
            ("definition", "define", [r"\bque es\b", r"\bqué es\b"]),
            ("author", "identify", [r"\bde quien es\b", r"\bde quién es\b", r"\bautor\b", r"\bescribio\b", r"\bescribió\b"]),
            ("director", "identify", [r"\bdirige\b", r"\bdirector\b", r"\bdirectora\b"]),
            ("date", "inform", [r"\bcuando\b", r"\bcuándo\b", r"\bfecha\b", r"\bestreno\b", r"\blanzamiento\b"]),
            ("price", "inform", [r"\bcuanto cuesta\b", r"\bcuánto cuesta\b", r"\bprecio\b", r"\bvale\b"]),
        ]

        for rel, rel_goal, patterns in relation_map:
            if any(re.search(p, low) for p in patterns):
                relation = rel
                goal = rel_goal
                break

        if any(x in low for x in ["compara", "comparar", "comparación", "comparacion", " versus ", " vs "]):
            goal = "compare"

        if any(x in low for x in ["explica", "explícame", "explicame", "por qué", "por que", "como funciona", "cómo funciona"]):
            goal = "explain"

        if any(x in low for x in ["nadie sabe", "poca gente", "poco conocidas", "poco conocidos", "curiosidades", "datos curiosos"]):
            goal = "discover"

        recent_markers = [
            "noticia", "noticias", "novedad", "novedades", "últimas", "ultimas",
            "último", "ultimo", "reciente", "recientes", "actualidad",
            "actualizaciones", "anuncios", "esta semana",
        ]

        if any(x in low for x in recent_markers):
            temporal_focus = "recent"
        elif any(x in low for x in ["actual", "actualmente", "ahora", "hoy"]):
            temporal_focus = "current"
        elif relation in {"identity", "definition"}:
            # "Quién es X" / "Qué es X" normally expects a current description.
            # Static relations such as author/director/date keep temporal_focus=any.
            temporal_focus = "current"
        else:
            temporal_focus = "any"

        depth = 1

        if any(x in low for x in [
            "investiga a fondo", "profundiza", "análisis profundo", "analisis profundo",
            "detalladamente", "todo lo que se sabe", "exhaustivo",
        ]):
            depth = 3
        elif any(x in low for x in [
            "analiza", "compara", "explica", "explícame", "explicame",
            "por qué", "por que", "impacto", "consecuencias", "importancia",
        ]):
            depth = 2
        elif temporal_focus == "recent" and count > 1:
            depth = 2

        diversity = "high" if count > 1 else ("medium" if goal in {"compare", "discover"} else "low")
        novelty = "high" if goal == "discover" else "normal"

        if temporal_focus == "recent":
            unit_type = "event"
        elif relation:
            unit_type = "fact"
        elif goal == "compare":
            unit_type = "entity"
        else:
            unit_type = "mixed"

        # Compatibility only; downstream architecture uses generic fields above.
        is_news = temporal_focus == "recent" and unit_type == "event"
        is_complex = depth >= 2

        topic_source = re.sub(r"\b\d{1,2}\b", " ", cleaned)

        controls = {
            "dime", "di", "busca", "buscar", "investiga", "investigar",
            "noticia", "noticias", "novedad", "novedades", "reciente", "recientes",
            "últimas", "ultimas", "último", "ultimo", "actualidad", "actualizaciones",
            "anuncios", "que", "qué", "quien", "quién", "de", "del", "la", "el",
            "los", "las", "sobre", "acerca", "cosas", "datos", "hechos",
        }

        words = re.findall(r"[\wáéíóúñÁÉÍÓÚÑ.-]+", topic_source)
        kept = [w for w in words if normalize(w) not in controls and len(normalize(w)) > 1]
        topic = " ".join(kept).strip() or cleaned

        return QueryIntent(
            original=original,
            cleaned=cleaned,
            topic=topic,
            topic_tokens=tokens(topic),
            count=count,
            is_news=is_news,
            is_complex=is_complex,
            goal=goal,
            relation=relation,
            temporal_focus=temporal_focus,
            diversity=diversity,
            depth=depth,
            unit_type=unit_type,
            novelty=novelty,
            explicit_count=explicit_count,
            requires_web=True,
        )


# ============================================================
# SEARCH DISCOVERY
# ============================================================

@dataclass
class WorkBudget:
    search_queries: int
    max_ranked: int
    fetch_articles: bool
    max_articles: int
    max_units: int
    max_context_chars: int


class ExecutionPlanner:
    def budget(self, intent: QueryIntent) -> WorkBudget:
        if intent.depth <= 1:
            return WorkBudget(
                search_queries=2,
                max_ranked=10,
                fetch_articles=False,
                max_articles=0,
                max_units=max(2, intent.count + 1),
                max_context_chars=900,
            )

        if intent.depth == 2:
            return WorkBudget(
                search_queries=4 if intent.count <= 3 else 6,
                max_ranked=22,
                fetch_articles=True,
                max_articles=min(8, max(4, intent.count + 3)),
                max_units=max(intent.count + 3, 6),
                max_context_chars=1500,
            )

        return WorkBudget(
            search_queries=7,
            max_ranked=32,
            fetch_articles=True,
            max_articles=min(12, max(7, intent.count + 5)),
            max_units=max(intent.count + 5, 9),
            max_context_chars=2200,
        )


class SearchPlanner:
    def build(self, intent: QueryIntent, budget: WorkBudget) -> List[Tuple[str, str]]:
        topic = intent.topic.strip() or intent.cleaned.strip()
        queries = []

        current_year = datetime.now(timezone.utc).year

        if intent.temporal_focus == "recent":
            queries.extend([
                (f'"{topic}" últimas novedades {current_year}', "es"),
                (f'"{topic}" latest updates {current_year}', "en"),
                (f'"{topic}" anuncios recientes {current_year}', "es"),
                (f'"{topic}" recent developments {current_year}', "en"),
                (f'"{topic}" actualidad {current_year}', "es"),
                (f'"{topic}" latest news {current_year}', "en"),
            ])
        elif intent.temporal_focus == "current":
            queries.extend([
                (f'"{topic}" actualidad {current_year}', "es"),
                (f'"{topic}" current {current_year}', "en"),
                (intent.cleaned, "es"),
            ])
        elif intent.novelty == "high":
            queries.extend([
                (f'"{topic}" datos poco conocidos', "es"),
                (f'"{topic}" lesser known facts', "en"),
                (f'"{topic}" curiosidades', "es"),
                (f'"{topic}" obscure facts', "en"),
            ])
        elif intent.goal == "compare":
            queries.extend([
                (intent.cleaned, "es"),
                (f'"{topic}" comparación', "es"),
                (f'"{topic}" comparison', "en"),
            ])
        else:
            queries.extend([
                (intent.cleaned, "es"),
                (f'"{topic}"', "es"),
                (f'"{topic}" overview', "en"),
            ])

        out = []
        seen = set()

        for query, language in queries:
            key = (normalize(query), language)
            if key in seen:
                continue
            seen.add(key)
            out.append((query, language))
            if len(out) >= budget.search_queries:
                break

        return out



class SearXNGClient:
    def health(self) -> bool:
        try:
            return requests.get(SEARXNG_HOME, timeout=3).status_code == 200
        except Exception:
            return False

    def _run(self, query: str, language: str, time_range: Optional[str] = None) -> List[SearchResult]:
        response = requests.get(
            SEARXNG_URL,
            params={
                "q": query,
                "format": "json",
                "language": language,
                "safesearch": 1,
                **({"time_range": time_range} if time_range else {}),
            },
            timeout=SEARCH_TIMEOUT,
        )

        response.raise_for_status()
        data = response.json()

        results = []

        for raw in data.get("results", [])[:RAW_RESULTS_PER_QUERY]:
            results.append(
                SearchResult(
                    title=clean(raw.get("title", ""), 350),
                    url=raw.get("url", "") or "",
                    content=clean(raw.get("content", ""), 1200),
                    engine=raw.get("engine", "") or "",
                    published_date=(
                        raw.get("publishedDate")
                        or raw.get("published_date")
                        or raw.get("pubdate")
                        or ""
                    ),
                    query_used=query,
                    language=language,
                )
            )

        return results

    def search(
        self,
        intent: QueryIntent,
        queries: Optional[List[Tuple[str, str]]] = None,
    ) -> List[SearchResult]:
        queries = queries or [(intent.cleaned, "es")]
        results = []

        max_workers = min(8, max(1, len(queries)))

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_map = {
                pool.submit(self._run, query, language, None): (query, language)
                for query, language in queries
            }

            for future in as_completed(future_map):
                query, language = future_map[future]

                try:
                    batch = future.result()

                    for item in batch:
                        item.query_used = query
                        item.language = language

                    results.extend(batch)

                except Exception as exc:
                    print(f"[SEARCH] {query}: {exc}")

        return results


# ============================================================
# SEARCH RESULT QUALITY + RANKING
# ============================================================

class ResultRanker:
    def topic_match(self, result: SearchResult, intent: QueryIntent) -> bool:
        topic = set(intent.topic_tokens)

        if not topic:
            return True

        haystack = set(tokens(f"{result.title} {result.content}"))

        if len(topic) == 1:
            return bool(topic & haystack)

        needed = max(1, (len(topic) + 1) // 2)
        return len(topic & haystack) >= needed

    def quality_ok(self, result: SearchResult, intent: QueryIntent) -> bool:
        if not result.url:
            return False

        if not self.topic_match(result, intent):
            return False

        if intent.temporal_focus not in {"recent"}:
            return True

        if result.domain in SOCIAL_DOMAINS:
            return False

        lower_url = result.url.lower()

        if any(marker in lower_url for marker in LOW_VALUE_URL_MARKERS):
            return False

        if not result.title or not result.content:
            return False

        if len(result.content) < 70:
            return False

        if is_generic(f"{result.title} {result.content}"):
            return False

        return True

    def score(self, result: SearchResult, intent: QueryIntent) -> float:
        topic = set(intent.topic_tokens)
        title_tokens = set(tokens(result.title))
        content_tokens = set(tokens(result.content))

        score = 0.0
        score += 6.0 * len(topic & title_tokens)
        score += 2.0 * len(topic & content_tokens)

        if result.published_date:
            score += 6.0

        if intent.temporal_focus == "recent":
            bucket = freshness_bucket(result.published_date)

            if bucket == 0:
                score += 12.0
            elif bucket == 1:
                score += 2.0
            else:
                score -= 12.0

        elif intent.temporal_focus == "current":
            confidence, age, _ = freshness_confidence(
                result.published_date,
                result.url,
                result.title,
                result.content,
            )

            # Current factual descriptions prefer fresher pages, but unlike
            # breaking/recent requests they are not hard-limited to 30 days.
            score += confidence * 7.0

            if age is not None:
                if age <= 90:
                    score += 5.0
                elif age <= 365:
                    score += 2.0
                elif age > 730:
                    score -= 6.0

        combined = f"{result.title} {result.content} {result.published_date}"

        if intent.temporal_focus == "recent" and re.search(
            r"\b(hoy|ayer|today|yesterday|hace\s+\d+\s+"
            r"(?:minuto|minutos|hora|horas|día|días|semana|semanas)|"
            r"\d+\s+(?:minutes?|hours?|days?|weeks?)\s+ago|2026)\b",
            combined,
            flags=re.IGNORECASE,
        ):
            score += 4.0

        if len(result.content) >= 120:
            score += 1.0

        return score

    def rank(self, results: List[SearchResult], intent: QueryIntent) -> List[SearchResult]:
        accepted = []

        for result in results:
            if not self.quality_ok(result, intent):
                continue

            if intent.temporal_focus == "recent" and STRICT_NEWS_FRESHNESS:
                if not result_fresh_enough(result, strict=True):
                    continue

            result.score = self.score(result, intent)

            if intent.temporal_focus in {"recent", "current"}:
                confidence, age, reason = freshness_confidence(
                    result.published_date,
                    result.url,
                    result.title,
                    result.content,
                )
                result.score += confidence * 12.0

            accepted.append(result)

        accepted.sort(key=lambda item: item.score, reverse=True)

        final = []
        seen_urls = set()
        seen_documents = []

        for result in accepted:
            url_key = result.url.split("#")[0].rstrip("/").lower()
            document = f"{result.title} {result.content}"

            if url_key in seen_urls:
                continue

            if any(similarity(document, old) >= 0.72 for old in seen_documents):
                continue

            seen_urls.add(url_key)
            seen_documents.append(document)
            final.append(result)

            if len(final) >= MAX_RANKED_RESULTS:
                break

        return final


# ============================================================
# HTML PARSER
# ============================================================

class ArticleHTMLParser(HTMLParser):
    """
    Parse structure instead of stripping the whole page blindly.
    Collects paragraphs, headings, title, metadata and JSON-LD.
    """

    SKIP_TAGS = {
        "script", "style", "noscript", "svg", "form",
        "nav", "footer", "header", "aside",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)

        self.skip_depth = 0
        self.current_tag = ""
        self.current_text = []
        self.current_attrs: Dict[str, str] = {}

        self.title_parts = []
        self.paragraphs = []
        self.headings = []
        self.meta = {}
        self.jsonld_blocks = []

        self.in_title = False
        self.in_jsonld = False
        self.jsonld_buffer = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.current_tag = tag
        self.current_attrs = attrs_dict

        if tag in self.SKIP_TAGS:
            self.skip_depth += 1

        if tag == "title":
            self.in_title = True

        if tag == "meta":
            key = (
                attrs_dict.get("property")
                or attrs_dict.get("name")
                or ""
            ).lower()

            content = attrs_dict.get("content", "")

            if key and content:
                self.meta[key] = clean(content, 500)

        if tag == "script":
            script_type = (attrs_dict.get("type") or "").lower()

            if script_type == "application/ld+json":
                self.in_jsonld = True
                self.jsonld_buffer = []

        if tag in {"p", "h1", "h2", "h3"}:
            self.current_text = []

    def handle_data(self, data):
        if self.in_jsonld:
            self.jsonld_buffer.append(data)
            return

        if self.skip_depth > 0:
            return

        if self.in_title:
            self.title_parts.append(data)

        if self.current_tag in {"p", "h1", "h2", "h3"}:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.in_jsonld:
            raw = "".join(self.jsonld_buffer).strip()

            if raw:
                self.jsonld_blocks.append(raw)

            self.in_jsonld = False
            self.jsonld_buffer = []

        if tag == "title":
            self.in_title = False

        if tag in {"p", "h1", "h2", "h3"}:
            text = clean(" ".join(self.current_text), 2500)

            if text:
                if tag == "p":
                    self.paragraphs.append(text)
                else:
                    self.headings.append(text)

            self.current_text = []

        if tag in self.SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1

        self.current_tag = ""

    @property
    def page_title(self) -> str:
        return clean(" ".join(self.title_parts), 400)


# ============================================================
# ARTICLE EXTRACTION
# ============================================================

class ArticleExtractor:
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/127 Safari/537.36"
        ),
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }

    def _parse_jsonld(self, blocks: List[str]) -> List[dict]:
        articles = []

        for raw in blocks:
            try:
                data = json.loads(raw)
            except Exception:
                continue

            stack = data if isinstance(data, list) else [data]

            while stack:
                item = stack.pop()

                if isinstance(item, list):
                    stack.extend(item)
                    continue

                if not isinstance(item, dict):
                    continue

                graph = item.get("@graph")

                if isinstance(graph, list):
                    stack.extend(graph)

                item_type = item.get("@type", "")
                types = item_type if isinstance(item_type, list) else [item_type]

                if any(
                    value in {"NewsArticle", "Article", "ReportageNewsArticle"}
                    for value in types
                ):
                    articles.append(item)

        return articles

    def _paragraph_score(
        self,
        paragraph: str,
        index: int,
        intent: QueryIntent,
    ) -> float:
        if len(paragraph) < 60:
            return -100.0

        if is_generic(paragraph):
            return -100.0

        boiler = boilerplate_score(paragraph)

        if boiler >= 2:
            return -100.0

        score = 0.0

        words = paragraph.split()

        # Paragraphs with actual prose.
        if len(words) >= 18:
            score += 2.0

        if len(words) >= 35:
            score += 1.0

        # Earlier paragraphs tend to contain the news lead.
        score += max(0.0, 4.0 - (index * 0.22))

        topic = set(intent.topic_tokens)
        paragraph_tokens = set(tokens(paragraph))

        score += 4.0 * len(topic & paragraph_tokens)

        # Sentences with verbs/punctuation are more likely editorial prose.
        if "." in paragraph:
            score += 1.0

        # Too many separators often means navigation/listing.
        if paragraph.count("·") >= 2 or paragraph.count("|") >= 2:
            score -= 5.0

        return score

    def _select_paragraphs(
        self,
        paragraphs: List[str],
        intent: QueryIntent,
    ) -> List[str]:
        cleaned = []
        seen = []

        for paragraph in paragraphs:
            paragraph = clean(paragraph, 3000)

            if not paragraph:
                continue

            if len(paragraph) < 80:
                continue

            if is_generic(paragraph):
                continue

            if boilerplate_score(paragraph) >= 2:
                continue

            normalized = normalize(paragraph)

            if any(marker in normalized for marker in [
                "marvel unlimited", "instant access", "exclusive deals",
                "member only", "member-only", "subscribe", "suscribete",
                "suscríbete", "cookies", "privacy policy",
            ]):
                continue

            # A paragraph should contain at least one complete sentence.
            if not split_sentences(paragraph):
                continue

            if any(similarity(paragraph, old) >= 0.82 for old in seen):
                continue

            seen.append(paragraph)
            cleaned.append(paragraph)

        scored = [
            (
                self._paragraph_score(paragraph, index, intent),
                index,
                paragraph,
            )
            for index, paragraph in enumerate(cleaned[:MAX_PARAGRAPHS_PER_ARTICLE])
        ]

        scored = [item for item in scored if item[0] > -50]

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = scored[:10]
        selected.sort(key=lambda item: item[1])

        return [item[2] for item in selected]

    def extract(
        self,
        result: SearchResult,
        intent: QueryIntent,
    ) -> Optional[Article]:
        try:
            response = requests.get(
                result.url,
                headers=self.HEADERS,
                timeout=ARTICLE_TIMEOUT,
                allow_redirects=True,
            )

            response.raise_for_status()

            content_type = (response.headers.get("content-type") or "").lower()

            if "text/html" not in content_type:
                return None

            html = response.text

            if len(html) < 1200:
                return None

            parser = ArticleHTMLParser()
            parser.feed(html)

            json_articles = self._parse_jsonld(parser.jsonld_blocks)

            title = ""
            published_date = ""
            paragraphs = []

            # Priority 1: structured NewsArticle.
            if json_articles:
                best = max(
                    json_articles,
                    key=lambda item: len(str(item.get("articleBody", ""))),
                )

                title = clean(
                    str(best.get("headline") or best.get("name") or ""),
                    400,
                )

                published_date = clean(
                    str(
                        best.get("datePublished")
                        or best.get("dateModified")
                        or ""
                    ),
                    120,
                )

                article_body = clean(
                    str(best.get("articleBody") or ""),
                    MAX_ARTICLE_TEXT,
                )

                if article_body:
                    # JSON-LD articleBody is often one giant block. Convert it
                    # into complete-sentence pseudo-paragraphs instead of
                    # feeding a raw wall of text into the evidence layer.
                    body_sentences = split_sentences(article_body)

                    if body_sentences:
                        paragraphs = body_sentences

            # Priority 2: metadata/title + real <p> elements.
            if not title:
                title = (
                    parser.meta.get("og:title")
                    or parser.meta.get("twitter:title")
                    or parser.page_title
                    or result.title
                )

            if not published_date:
                published_date = (
                    parser.meta.get("article:published_time")
                    or parser.meta.get("datepublished")
                    or parser.meta.get("date")
                    or parser.meta.get("pubdate")
                    or result.published_date
                )

            if not paragraphs:
                paragraphs = parser.paragraphs

            selected_paragraphs = self._select_paragraphs(
                paragraphs,
                intent,
            )

            if not selected_paragraphs:
                return None

            # Real article-level topic verification.
            article_preview = " ".join(selected_paragraphs[:8])
            article_tokens = set(tokens(f"{title} {article_preview}"))
            topic = set(intent.topic_tokens)

            if topic:
                if len(topic) == 1:
                    if not (topic & article_tokens):
                        return None
                else:
                    needed = max(1, (len(topic) + 1) // 2)

                    if len(topic & article_tokens) < needed:
                        return None

            final_url = response.url or result.url

            return Article(
                title=clean(title, 400),
                url=final_url,
                domain=urlparse(final_url).netloc.lower().replace("www.", ""),
                paragraphs=selected_paragraphs,
                published_date=published_date,
                score=result.score,
            )

        except Exception as exc:
            print(f"[ARTICLE] {result.domain}: {exc}")
            return None

    def extract_many(
        self,
        results: List[SearchResult],
        intent: QueryIntent,
    ) -> List[Article]:
        if not results:
            return []

        fetch_limit = min(
            len(results),
            max(MAX_ARTICLES_TO_FETCH, intent.count * 2),
        )

        candidates = results[:fetch_limit]
        extracted = []

        with ThreadPoolExecutor(max_workers=ARTICLE_FETCH_WORKERS) as pool:
            future_map = {
                pool.submit(self.extract, result, intent): result
                for result in candidates
            }

            for future in as_completed(future_map):
                try:
                    article = future.result()
                except Exception as exc:
                    print(f"[ARTICLE] worker: {exc}")
                    continue

                if not article:
                    continue

                if intent.is_news and STRICT_NEWS_FRESHNESS:
                    if not article_fresh_enough(article, strict=True):
                        continue

                extracted.append(article)

        # Freshness confidence + search score determine final order.
        def article_sort_key(article):
            if not intent.is_news:
                return -article.score

            confidence, age, _ = freshness_confidence(
                article.published_date,
                article.url,
                article.title,
                " ".join(article.paragraphs[:2]),
            )

            age_value = age if age is not None else 9999
            return (-confidence, age_value, -article.score)

        extracted.sort(key=article_sort_key)

        articles = []
        seen_urls = set()
        seen_articles = []
        domain_counts = {}

        for article in extracted:
            url_key = article.url.split("#")[0].rstrip("/").lower()

            if url_key in seen_urls:
                continue

            # Keep domain diversity, but allow a second result if otherwise
            # Jarvis cannot satisfy the requested number.
            domain_limit = 1 if len(extracted) >= intent.count else 2
            count_for_domain = domain_counts.get(article.domain, 0)

            if intent.is_news and count_for_domain >= domain_limit:
                continue

            signature = f"{article.title} {' '.join(article.paragraphs[:3])}"

            if any(similarity(signature, old) >= 0.66 for old in seen_articles):
                continue

            seen_urls.add(url_key)
            seen_articles.append(signature)
            domain_counts[article.domain] = count_for_domain + 1
            articles.append(article)

            if len(articles) >= max(intent.count + 2, intent.count):
                break

        return articles


# ============================================================
# EVIDENCE / EVENT SELECTION
# ============================================================

class EvidenceBuilder:
    def _paragraph_relevance(
        self,
        paragraph: str,
        article: Article,
        intent: QueryIntent,
        paragraph_index: int,
    ) -> float:
        paragraph_tokens = set(tokens(paragraph))
        title_tokens = set(tokens(article.title))
        topic = set(intent.topic_tokens)

        score = 0.0
        score += 6.0 * len(topic & paragraph_tokens)
        score += 2.5 * len(topic & title_tokens)
        score += max(0.0, 5.0 - paragraph_index * 0.45)

        sentences = split_sentences(paragraph)

        if len(sentences) >= 2:
            score += 2.0

        if len(paragraph.split()) >= 35:
            score += 1.0

        if boilerplate_score(paragraph) >= 1:
            score -= 6.0

        return score

    def _context_from_article(
        self,
        article: Article,
        intent: QueryIntent,
    ) -> Optional[str]:
        candidates = []

        for index, paragraph in enumerate(article.paragraphs[:12]):
            complete_sentences = split_sentences(paragraph)

            if not complete_sentences:
                continue

            # Build a coherent block of up to 4 complete sentences.
            block = " ".join(complete_sentences[:4]).strip()

            if len(block) < 120:
                continue

            score = self._paragraph_relevance(
                block,
                article,
                intent,
                index,
            )

            candidates.append((score, index, block))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0], reverse=True)
        best_score, best_index, best_block = candidates[0]

        if best_score < 0:
            return None

        # Add one nearby block if it gives extra context.
        context_parts = [best_block]

        nearby = sorted(
            candidates[1:],
            key=lambda item: abs(item[1] - best_index),
        )

        for score, index, block in nearby:
            if abs(index - best_index) > 2:
                continue

            if score < 0:
                continue

            if similarity(block, best_block) >= 0.65:
                continue

            context_parts.append(block)
            break

        combined = " ".join(context_parts)
        sentences = split_sentences(combined)

        if not sentences:
            return None

        # Context must end on a complete sentence, never by character count.
        return " ".join(sentences[:6]).strip()

    def build(
        self,
        articles: List[Article],
        intent: QueryIntent,
    ) -> List[Evidence]:
        evidence = []
        seen_events = []

        for article in articles:
            context = self._context_from_article(article, intent)

            if not context:
                continue

            context_sentences = split_sentences(context)

            if not context_sentences:
                continue

            statement = context_sentences[0]

            if any(
                similarity(statement, previous) >= 0.42
                for previous in seen_events
            ):
                continue

            seen_events.append(statement)

            evidence.append(
                Evidence(
                    statement=statement,
                    context=context,
                    title=article.title,
                    url=article.url,
                    domain=article.domain,
                    published_date=article.published_date,
                    score=article.score,
                    uncertain=has_uncertainty(context),
                )
            )

            if len(evidence) >= max(intent.count * 2, 8):
                break

        return evidence


class SearchSnippetEvidenceBuilder:
    """
    Conservative fallback for fresh news whose publisher blocks direct article
    extraction (403/429/paywall). Uses only SearXNG title + snippet.
    """

    def build(
        self,
        results: List[SearchResult],
        intent: QueryIntent,
        existing: List[Evidence],
    ) -> List[Evidence]:
        if not intent.is_news:
            return []

        output = []
        seen = [item.statement for item in existing]

        for result in results:
            if len(existing) + len(output) >= max(intent.count * 3, intent.count + 8):
                break

            confidence, age, _ = freshness_confidence(
                result.published_date,
                result.url,
                result.title,
                result.content,
            )

            if confidence < 0.60:
                continue

            if age is not None and age > NEWS_FRESH_DAYS + 2:
                continue

            title_tokens = set(tokens(result.title))
            topic_tokens = set(intent.topic_tokens)

            # Snippet-only evidence needs a stronger topical requirement.
            if topic_tokens and not (topic_tokens & title_tokens):
                continue

            title = clean(result.title, 500)
            snippet = sanitize_search_snippet(result.content)

            if not title or not snippet:
                continue

            if is_generic(f"{title} {snippet}"):
                continue

            if is_vague_event_text(title):
                continue

            statement = title
            context = f"{title}. {snippet}"

            # Reject generic "Marvel news/updates" pages even if recent.
            probe = Evidence(
                statement=statement,
                context=context,
                title=title,
                url=result.url,
                domain=result.domain,
                published_date=result.published_date,
                score=result.score,
                uncertain=has_uncertainty(context),
            )

            if not evidence_specific_enough(probe):
                continue

            if any(
                similarity(statement, previous) >= 0.50
                for previous in seen
            ):
                continue

            seen.append(statement)

            output.append(
                Evidence(
                    statement=statement,
                    context=context,
                    title=title,
                    url=result.url,
                    domain=result.domain,
                    published_date=result.published_date,
                    score=result.score - 2.0,
                    uncertain=has_uncertainty(context),
                )
            )

        return output





# ============================================================
# EVENT CLUSTERING
# ============================================================

class EventClusterer:
    """
    Una noticia = un acontecimiento. Varias fuentes del mismo hecho se agrupan.
    El método es genérico: usa similitud textual y entidades, no listas por tema.
    """

    def _event_text(self, item: Evidence) -> str:
        return clean(f"{item.title}. {item.statement}. {item.context}", 2600)

    def _same_event(self, a: Evidence, b: Evidence) -> bool:
        ta = self._event_text(a)
        tb = self._event_text(b)

        sim = similarity(ta, tb)
        if sim >= 0.44:
            return True

        if similarity(a.title, b.title) >= 0.50:
            return True

        ents_a = extract_named_tokens(ta)
        ents_b = extract_named_tokens(tb)
        common = ents_a & ents_b

        if common and sim >= 0.28:
            return True

        return False

    def unique_events(self, evidence: List[Evidence], limit: int) -> List[Evidence]:
        clusters = []

        for item in sorted(evidence, key=lambda x: x.score, reverse=True):
            placed = False

            for group in clusters:
                if any(self._same_event(item, other) for other in group):
                    group.append(item)
                    placed = True
                    break

            if not placed:
                clusters.append([item])

        representatives = [
            max(group, key=lambda x: x.score)
            for group in clusters
        ]
        representatives.sort(key=lambda x: x.score, reverse=True)
        return representatives[:limit]


# ============================================================
# SEARCH SNIPPET SANITATION
# ============================================================

SEARCH_UI_PATTERNS = [
    r"\bNoticias hoy\b",
    r"\bEn vivo\b",
    r"\bAgregar [A-Za-zÁÉÍÓÚÑáéíóúñ ]+ en Google\b",
    r"\bEspectáculos\b",
    r"\bEspectaculos\b",
    r"\bÚltimas noticias\b",
    r"\bUltimas noticias\b",
    r"\bNewsletter\b",
    r"\bIniciar sesión\b",
    r"\bIniciar sesion\b",
    r"\bSuscríbete\b",
    r"\bSuscribete\b",
    r"\bCompartir\b",
    r"\bFacebook\b",
    r"\bTwitter\b",
    r"\bTelegram\b",
    r"\bWhatsApp\b",
]

DATE_FRAGMENT_PATTERNS = [
    r"\b\d{1,2}\s+(?:ene|feb|mar|abr|may|jun|jul|ago|sep|sept|oct|nov|dic)\s+20\d{2}\b",
    r"\b\d{1,2}\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+20\d{2}\b",
    r"\b20\d{2}-\d{2}-\d{2}(?:T[0-9:+\-.Z]+)?\b",
]


def sanitize_search_snippet(text: str) -> str:
    """
    Clean search-engine snippets before they are given to the model.
    Removes navigation/date/UI debris without inventing missing content.
    """
    if not text:
        return ""

    value = unescape(str(text))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    # Common UI/navigation fragments.
    for pattern in SEARCH_UI_PATTERNS:
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)

    # Search-result dates should remain internal metadata, not model context.
    for pattern in DATE_FRAGMENT_PATTERNS:
        value = re.sub(pattern, " ", value, flags=re.IGNORECASE)

    # Bulleted / breadcrumb-like debris.
    value = re.sub(r"\s*[·|•]\s*", ". ", value)
    value = re.sub(r"\.{2,}", ". ", value)
    value = re.sub(r"\s+", " ", value).strip(" .,-–—:")

    # Keep only substantive clauses. Search snippets are often incomplete, so
    # do not require terminal punctuation here; the model will summarize them.
    chunks = re.split(r"(?<=[.!?])\s+|\s{2,}", value)

    useful = []

    for chunk in chunks:
        chunk = clean(chunk, 900)

        if len(chunk) < 35:
            continue

        if is_generic(chunk):
            continue

        if boilerplate_score(chunk) >= 2:
            continue

        useful.append(chunk)

        if len(useful) >= 3:
            break

    if useful:
        return " ".join(useful)

    return clean(value, 1200)


def context_adds_information(event: str, context: str) -> bool:
    """
    Context should add information, not merely restate the event.
    """
    if not context:
        return False

    if similarity(event, context) >= 0.58:
        return False

    event_tokens = set(tokens(event))
    context_tokens = set(tokens(context))

    new_tokens = context_tokens - event_tokens

    # Need at least a few substantive new words to justify another sentence.
    return len(new_tokens) >= 4


def user_facing_text_clean(text: str) -> bool:
    if not text:
        return False

    low = normalize(text)

    if any(normalize(p) in low for p in [
        "noticias hoy",
        "en vivo",
        "agregar clarin en google",
        "agregar clarín en google",
        "espectaculos",
        "espectáculos",
        "newsletter",
        "suscribete",
        "suscríbete",
    ]):
        return False

    if boilerplate_score(text) >= 2:
        return False

    return True


# ============================================================
# EVENT SPECIFICITY
# ============================================================

VAGUE_EVENT_PATTERNS = [
    "novedades marvel",
    "nuevas noticias",
    "actualizaciones sobre",
    "sorprendente aparición",
    "sorprendente aparicion",
    "revolucionando el evento",
    "se presentaron novedades",
    "se anunciaron novedades",
    "más información",
    "mas informacion",
    "últimas novedades",
    "ultimas novedades",
]

ACTION_WORDS_ES = {
    "anunció", "anuncio", "presentó", "presento", "confirmó", "confirmo",
    "reveló", "revelo", "estrenó", "estreno", "publicó", "publico",
    "lanzó", "lanzo", "mostró", "mostro", "adelantó", "adelanto",
    "canceló", "cancelo", "retrasó", "retraso", "renovó", "renovo",
    "fichó", "ficho", "regresará", "regresara", "volverá", "volvera",
    "inició", "inicio", "comenzó", "comenzo", "terminó", "termino",
    "debutó", "debuto", "incorporó", "incorporo",
}

ACTION_WORDS_EN = {
    "announced", "revealed", "confirmed", "released", "launched", "showed",
    "unveiled", "delayed", "cancelled", "canceled", "renewed", "cast",
    "returns", "returning", "premiered", "debuted", "joined",
}


def is_vague_event_text(text: str) -> bool:
    n = normalize(text)

    if any(normalize(pattern) in n for pattern in VAGUE_EVENT_PATTERNS):
        return True

    words = set(re.findall(r"[a-záéíóúñ]+", n))
    action_hits = len(words & (ACTION_WORDS_ES | ACTION_WORDS_EN))

    # A user-facing news event needs some concrete action or a sufficiently
    # specific title/project/person signal.
    named = extract_named_tokens(text)
    quoted = re.findall(r'["“”\']([^"“”\']{3,80})["“”\']', text or "")

    if action_hits == 0 and len(named) < 2 and not quoted:
        return True

    return False


def evidence_specific_enough(item: Evidence) -> bool:
    combined = f"{item.title}. {item.context}"

    if is_generic(combined):
        return False

    if is_vague_event_text(combined):
        return False

    # Headline should contain more than just the broad topic.
    title_key = set(tokens(item.title))
    if len(title_key) < 2:
        return False

    return True


def summary_specific_enough(summary: str, evidence_text: str) -> bool:
    if is_vague_event_text(summary):
        return False

    # Require meaningful lexical grounding beyond generic topic words.
    summary_tokens = set(tokens(summary))
    evidence_tokens = set(tokens(evidence_text))

    overlap = summary_tokens & evidence_tokens

    if len(overlap) < 3:
        return False

    return True



# ============================================================
# FINAL LANGUAGE / PRESENTATION GUARD
# ============================================================

ENGLISH_COMMON = {
    "the", "and", "with", "from", "this", "that", "new", "news", "full",
    "list", "august", "september", "october", "november", "december",
    "marvel", "comics", "movie", "movies", "series", "project", "projects",
    "announced", "revealed", "released", "launch", "launches", "latest",
    "more", "first", "look", "trailer", "return", "returns", "coming",
}


def english_word_ratio(text: str) -> float:
    words = re.findall(r"[a-z]+", (text or "").lower())

    if not words:
        return 0.0

    hits = sum(1 for word in words if word in ENGLISH_COMMON)
    return hits / max(1, len(words))


def final_is_spanish(text: str) -> bool:
    if not text:
        return False

    if looks_english(text):
        return False

    # Catch short English headlines that the previous heuristic missed.
    if english_word_ratio(text) >= 0.18:
        return False

    return True


def final_answer_quality(text: str, requested_count: int) -> bool:
    if not text or not final_is_spanish(text):
        return False

    low = normalize(text)

    forbidden = [
        "fuente:", "http://", "https://",
        "noticias hoy", "en vivo", "newsletter",
        "contexto verificado", "evidencia ",
    ]

    if any(item in low for item in forbidden):
        return False

    # Need real explanatory content, not bare headlines.
    numbered = re.split(r"\n\s*\n|\n(?=\d+\.)", text)
    items = [x.strip() for x in numbered if re.match(r"^\d+\.", x.strip())]

    if not items:
        return False

    for item in items:
        # At least ~2 complete sentences or one fairly developed paragraph.
        sentences = re.split(r"(?<=[.!?])\s+", item)
        complete = [
            s for s in sentences
            if len(s.split()) >= 8 and not looks_truncated(s)
        ]

        if len(complete) < 2 and len(item.split()) < 35:
            return False

        if not final_is_spanish(item):
            return False

    return True



# ============================================================
# FAST FACT QUERY SHAPE
# ============================================================

def factual_relation_from_question(question: str) -> str:
    q = normalize(question)
    if re.search(r"\b(quien es|quién es)\b", q): return "identity"
    if re.search(r"\b(que es|qué es)\b", q): return "definition"
    if re.search(r"\b(de quien es|de quién es|autor|escribio|escribió)\b", q): return "author"
    if re.search(r"\b(dirige|director|directora)\b", q): return "director"
    if re.search(r"\b(cuando|cuándo|fecha|salio|salió|sale)\b", q): return "date"
    if re.search(r"\b(cuanto cuesta|cuánto cuesta|precio|vale)\b", q): return "price"
    return "fact"

def compact_fact_context(text: str, relation: str, max_chars: int = 320) -> str:
    cleaned = sanitize_search_snippet(text) or clean(text, max_chars)
    sentences = split_sentences(cleaned)
    if not sentences:
        return clean(cleaned, max_chars)
    keywords = {
        "identity": ["es ", "futbolista", "actor", "actriz", "escritor", "empresa", "compañía", "cantante"],
        "definition": ["es ", "empresa", "compañía", "organización", "franquicia", "editorial"],
        "author": ["autor", "autora", "escribió", "escrito por"],
        "director": ["director", "dirige", "dirigida por", "dirigido por"],
        "date": ["fecha", "estreno", "lanzamiento", "publicó", "publicado"],
        "price": ["precio", "cuesta", "vale", "$", "€"],
        "fact": [],
    }.get(relation, [])
    ranked = []
    for idx, sentence in enumerate(sentences[:6]):
        n = normalize(sentence); score = 2 if idx == 0 else 0
        for keyword in keywords:
            if normalize(keyword) in n: score += 3
        if relation in {"identity", "definition"} and any(x in n for x in ["hijo de","hija de","hermano","hermana","padre","madre","representante","familia"]):
            score -= 4
        ranked.append((score, idx, sentence))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    chosen=[]; total=0
    for _,_,sentence in ranked:
        s=clean(sentence,max_chars)
        if not s: continue
        if total + len(s) > max_chars and chosen: continue
        chosen.append(s); total += len(s)+1
        if len(chosen) >= 2: break
    return " ".join(chosen)[:max_chars].strip()


# ============================================================
# GENERIC FACTUAL SEARCH EVIDENCE
# ============================================================

class GenericSearchEvidenceBuilder:
    """
    Evidence for ordinary factual questions from SearXNG title + snippet.
    Avoids opening publisher pages when the user only asks a simple fact such
    as "quién es Messi" or "quién dirige X".
    """

    def build(
        self,
        results: List[SearchResult],
        intent: QueryIntent,
        existing: List[Evidence],
        limit: int = 6,
    ) -> List[Evidence]:
        output = []
        seen = [item.statement for item in existing]

        for result in results:
            if len(existing) + len(output) >= limit:
                break

            title = clean(result.title, 500)
            relation = factual_relation_from_question(intent.original)
            snippet = compact_fact_context(result.content, relation, max_chars=420)

            if not title or not snippet:
                continue

            combined = f"{title}. {snippet}"

            if is_generic(combined):
                continue

            topic_tokens = set(intent.topic_tokens)
            combined_tokens = set(tokens(combined))

            if topic_tokens and not (topic_tokens & combined_tokens):
                continue

            if any(
                similarity(title, previous) >= 0.58
                for previous in seen
            ):
                continue

            seen.append(title)

            output.append(
                Evidence(
                    statement=title,
                    context=combined,
                    title=title,
                    url=result.url,
                    domain=result.domain,
                    published_date=result.published_date,
                    score=result.score - 1.0,
                    uncertain=has_uncertainty(combined),
                )
            )

        return output


# ============================================================
# OLLAMA
# ============================================================



class TemporalValidityEngine:
    """
    Generic temporal layer.

    It does not know anything about Marvel, SpaceX, football, etc.
    It operates on the query's temporal requirement and the evidence itself.
    """

    def _main_years(self, item: Evidence) -> set:
        # Title + statement represent the main claim more strongly than a long
        # article body that may contain historical background.
        # extract_years() returns strings, so normalize them to integers once.
        years = extract_years(f"{item.title} {item.statement}")
        output = set()

        for year in years:
            try:
                output.add(int(year))
            except (TypeError, ValueError):
                continue

        return output

    def valid(self, item: Evidence, intent: QueryIntent) -> bool:
        if intent.temporal_focus == "any":
            return True

        current_year = datetime.now(timezone.utc).year
        main_years = self._main_years(item)

        if intent.temporal_focus == "recent":
            confidence, age, _ = freshness_confidence(
                item.published_date,
                item.url,
                item.title,
                item.context,
            )

            # Recent requests require recent source evidence.
            if confidence < 0.55:
                return False

            if age is not None and age > NEWS_FRESH_DAYS + 5:
                return False

            # If the MAIN claim explicitly identifies only an old year, it is
            # a historical event, not a current news item.
            if main_years and current_year not in main_years:
                if max(main_years) < current_year:
                    return False

        elif intent.temporal_focus == "current":
            # Current entity descriptions may come from evergreen pages, but
            # explicit stale-year titles/statements are poor candidates.
            if main_years and max(main_years) <= current_year - 2:
                return False

        return True

    def _sentence_score(
        self,
        sentence: str,
        item: Evidence,
        intent: QueryIntent,
        index: int,
    ) -> float:
        s = normalize(sentence)
        score = 0.0
        current_year = datetime.now(timezone.utc).year

        if index == 0:
            score += 2.0

        title_tokens = set(tokens(item.title))
        sent_tokens = set(tokens(sentence))
        score += min(4.0, len(title_tokens & sent_tokens) * 0.8)

        if intent.temporal_focus in {"recent", "current"}:
            if str(current_year) in sentence:
                score += 5.0

            if re.search(
                r"\b(hoy|ayer|today|yesterday|reciente|recent|"
                r"esta semana|this week|anunció|presentó|lanzó|confirmó|"
                r"announced|launched|revealed|confirmed)\b",
                s,
            ):
                score += 3.0

        years = extract_years(sentence)

        if years:
            parsed_years = []

            for y in years:
                try:
                    parsed_years.append(int(y))
                except (TypeError, ValueError):
                    continue

            newest = max(parsed_years) if parsed_years else None

            if newest is not None:
                if intent.temporal_focus == "recent" and newest < current_year:
                    score -= 7.0
                elif intent.temporal_focus == "current" and newest <= current_year - 2:
                    score -= 4.0

        # Identity / definition answers should not center on old career/family
        # trivia when a current description is requested.
        if intent.relation in {"identity", "definition"}:
            if any(x in s for x in [
                "hijo de", "hija de", "hermano", "hermana",
                "padre", "madre", "family", "brother", "sister",
            ]):
                score -= 3.0

        return score

    def focus(self, item: Evidence, intent: QueryIntent) -> Evidence:
        if intent.temporal_focus == "any":
            return item

        sentences = split_sentences(item.context)

        if not sentences:
            return item

        scored = [
            (self._sentence_score(sentence, item, intent, idx), idx, sentence)
            for idx, sentence in enumerate(sentences[:10])
        ]
        scored.sort(key=lambda x: (-x[0], x[1]))

        chosen = []
        total = 0
        max_chars = 900 if intent.depth >= 2 else 520

        for score, _, sentence in scored:
            if score < -2:
                continue

            s = clean(sentence, max_chars)

            if not s:
                continue

            if total + len(s) > max_chars and chosen:
                continue

            chosen.append(s)
            total += len(s) + 1

            if len(chosen) >= (3 if intent.depth >= 2 else 2):
                break

        focused_context = " ".join(chosen).strip() or clean(item.context, max_chars)

        return Evidence(
            statement=item.statement,
            context=focused_context,
            title=item.title,
            url=item.url,
            domain=item.domain,
            published_date=item.published_date,
            score=item.score,
            uncertain=item.uncertain,
        )

    def apply(
        self,
        evidence: List[Evidence],
        intent: QueryIntent,
    ) -> List[Evidence]:
        output = []

        for item in evidence:
            if not self.valid(item, intent):
                continue

            output.append(self.focus(item, intent))

        return output



class ClaimConsensusEngine:
    """
    Generic factual consensus layer.

    It does not perform new searches and does not call Ollama.
    It only uses the evidence already retrieved to:
    - detect conflicting hard facts;
    - prefer values supported by more than one independent unit;
    - penalize isolated conflicting values;
    - attach a small factual-confidence bonus to corroborated units.

    This is intentionally conservative and cheap.
    """

    DATE_PATTERNS = [
        r"\b(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})\b",
        r"\b(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})\b",
        r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",
    ]

    NUMBER_CONTEXT_PATTERNS = [
        r"\b(\d{1,4})\s+(balones?|premios?|oscars?|óscars?|titulos?|títulos?|años?|millones?|billones?|acciones?|misiones?|lanzamientos?)\b",
        r"\b(\d{1,4})\s+(ballons?|awards?|titles?|years?|million|billion|missions?|launches?)\b",
    ]

    def _source_text(self, item: Evidence) -> str:
        return clean(
            f"{item.title}. {item.statement}. {item.context}",
            5000,
        )

    def _extract_hard_claims(self, item: Evidence) -> dict:
        text = self._source_text(item)
        low = normalize(text)

        claims = {
            "years": set(),
            "dates": set(),
            "quantities": set(),
        }

        for year in extract_years(text):
            try:
                claims["years"].add(int(year))
            except Exception:
                pass

        for pattern in self.DATE_PATTERNS:
            for match in re.findall(pattern, low, flags=re.IGNORECASE):
                if isinstance(match, tuple):
                    claims["dates"].add(tuple(str(x).lower() for x in match))
                else:
                    claims["dates"].add(str(match).lower())

        for pattern in self.NUMBER_CONTEXT_PATTERNS:
            for match in re.findall(pattern, low, flags=re.IGNORECASE):
                if isinstance(match, tuple):
                    value = str(match[0])
                    context = str(match[1]).lower()
                    claims["quantities"].add((value, context))

        return claims

    def _independent_key(self, item: Evidence) -> str:
        # Domain is a practical independence proxy for this local engine.
        return item.domain or item.url or item.title

    def apply(
        self,
        evidence: List[Evidence],
        intent: QueryIntent,
    ) -> List[Evidence]:
        if len(evidence) <= 1:
            return evidence

        item_claims = []
        support_years = defaultdict(set)
        support_dates = defaultdict(set)
        support_quantities = defaultdict(set)

        for item in evidence:
            claims = self._extract_hard_claims(item)
            source_key = self._independent_key(item)
            item_claims.append((item, claims))

            for value in claims["years"]:
                support_years[value].add(source_key)

            for value in claims["dates"]:
                support_dates[value].add(source_key)

            for value in claims["quantities"]:
                support_quantities[value].add(source_key)

        # Only form a consensus where at least two independent sources agree.
        consensus_years = {
            value
            for value, sources in support_years.items()
            if len(sources) >= 2
        }
        consensus_dates = {
            value
            for value, sources in support_dates.items()
            if len(sources) >= 2
        }
        consensus_quantities = {
            value
            for value, sources in support_quantities.items()
            if len(sources) >= 2
        }

        output = []

        for item, claims in item_claims:
            score = item.score

            if consensus_years and claims["years"]:
                if claims["years"] & consensus_years:
                    score += 1.5
                elif intent.temporal_focus in {"recent", "current"}:
                    score -= 2.5

            if consensus_dates and claims["dates"]:
                if claims["dates"] & consensus_dates:
                    score += 2.5
                else:
                    score -= 3.0

            if consensus_quantities and claims["quantities"]:
                if claims["quantities"] & consensus_quantities:
                    score += 2.0
                else:
                    score -= 2.5

            output.append(
                Evidence(
                    statement=item.statement,
                    context=item.context,
                    title=item.title,
                    url=item.url,
                    domain=item.domain,
                    published_date=item.published_date,
                    score=score,
                    uncertain=item.uncertain,
                )
            )

        output.sort(key=lambda x: x.score, reverse=True)
        return output



class HardUnitLimiter:
    """
    Final deterministic guard before generation.

    The LLM can never receive more answer slots than independent units.
    It also performs a final semantic duplicate collapse.
    """

    def collapse(
        self,
        evidence: List[Evidence],
        intent: QueryIntent,
    ) -> List[Evidence]:
        selected = []

        # Slightly stricter duplicate threshold for multi-item answers.
        duplicate_threshold = 0.42 if intent.count > 1 else 0.50

        for item in sorted(evidence, key=lambda x: x.score, reverse=True):
            item_text = f"{item.title}. {item.statement}. {item.context}"

            duplicate = False

            for old in selected:
                old_text = f"{old.title}. {old.statement}. {old.context}"

                if similarity(item_text, old_text) >= duplicate_threshold:
                    duplicate = True
                    break

                item_entities = extract_named_tokens(item_text)
                old_entities = extract_named_tokens(old_text)

                shared = item_entities & old_entities

                # Shared named entities + similar titles often means one event
                # described from two outlets.
                if shared and similarity(item.title, old.title) >= 0.34:
                    duplicate = True
                    break

            if duplicate:
                continue

            selected.append(item)

        return selected

    def answer_limit(
        self,
        evidence: List[Evidence],
        intent: QueryIntent,
    ) -> int:
        if not evidence:
            return 0

        if intent.count <= 1:
            return 1

        return min(intent.count, len(evidence))


class UnitSelector:
    """
    Universal deterministic selector.
    It does not know about Marvel/SpaceX/etc. It scores units against the plan.
    """

    EVENT_WORDS = {
        "anuncia", "anunció", "presenta", "presentó", "lanza", "lanzó",
        "confirma", "confirmó", "estrena", "estrenó", "publica", "publicó",
        "firma", "firmó", "compra", "compró", "adquiere", "adquirió",
        "revela", "reveló", "muestra", "mostró", "regresa", "regresó",
        "comienza", "comenzó", "termina", "terminó", "aprueba", "aprobó",
        "announces", "announced", "launches", "launched", "reveals", "revealed",
        "confirms", "confirmed", "releases", "released", "acquires", "acquired",
    }

    GENERIC_WORDS = {
        "overview", "wiki", "wikipedia", "historia", "history", "guía", "guide",
        "todo sobre", "everything about", "explicado", "explained",
    }

    def score(self, item: Evidence, intent: QueryIntent) -> float:
        text = normalize(f"{item.title} {item.context}")
        score = float(item.score)

        topic_hits = sum(1 for t in intent.topic_tokens if t in text)
        score += topic_hits * 1.5

        if intent.temporal_focus == "recent":
            if any(word in text for word in self.EVENT_WORDS):
                score += 3.0
            if item.published_date:
                score += 1.5

        if intent.novelty == "high":
            if any(word in text for word in ["curios", "lesser known", "poco conocido", "rare", "obscure"]):
                score += 1.0

        if any(word in text for word in self.GENERIC_WORDS):
            score -= 2.0

        if len(clean(item.context, 2000)) < 120:
            score -= 1.0

        return score

    def select(
        self,
        evidence: List[Evidence],
        intent: QueryIntent,
        limit: int,
    ) -> List[Evidence]:
        ranked = sorted(
            evidence,
            key=lambda x: self.score(x, intent),
            reverse=True,
        )

        selected = []

        for item in ranked:
            if any(
                similarity(
                    f"{item.title} {item.context}",
                    f"{old.title} {old.context}",
                ) >= 0.48
                for old in selected
            ):
                continue

            selected.append(item)

            if len(selected) >= limit:
                break

        return selected


class OllamaSynthesizer:
    def health(self) -> bool:
        try:
            return requests.get(
                OLLAMA_TAGS_URL,
                timeout=OLLAMA_HEALTH_TIMEOUT,
            ).status_code == 200
        except Exception:
            return False

    def _prepare_evidence(
        self,
        intent: QueryIntent,
        evidence: List[Evidence],
    ) -> List[Evidence]:
        prepared = []

        for item in evidence:
            if not evidence_specific_enough(item):
                continue

            context = sanitize_search_snippet(item.context)

            if not context:
                context = clean(item.context, 3200)

            candidate = Evidence(
                statement=item.statement,
                context=context,
                title=clean(item.title, 700),
                url=item.url,
                domain=item.domain,
                published_date=item.published_date,
                score=item.score,
                uncertain=item.uncertain,
            )

            if any(
                similarity(candidate.statement, old.statement) >= 0.50
                for old in prepared
            ):
                continue

            prepared.append(candidate)

            if len(prepared) >= max(intent.count + 4, 7):
                break

        return prepared

    def _normalize_evidence(
        self,
        intent: QueryIntent,
        prepared: List[Evidence],
    ) -> Optional[List[dict]]:
        """
        Stage 1:
        Convert raw web evidence to Spanish fact cards.
        This stage does NOT write the final answer.
        """
        blocks = []

        for index, item in enumerate(prepared, 1):
            blocks.append(
                f"[EVIDENCIA {index}]\n"
                f"TITULAR: {item.title}\n"
                f"CONTEXTO: {item.context}"
            )

        evidence_text = "\n\n".join(blocks)

        prompt = f"""
Eres el normalizador de evidencia de JARVIS.

Convierte cada evidencia útil en una ficha factual EN ESPAÑOL.
NO redactes todavía la respuesta final.

TEMA PRINCIPAL:
{intent.topic}

REGLAS:
- Usa exclusivamente lo que aparece en cada evidencia.
- Traduce al español cualquier contenido en inglés.
- No inventes datos.
- No mezcles evidencias.
- No añadas conocimiento previo.
- Elimina navegación, fechas técnicas, botones, menús y basura web.
- Si una evidencia es demasiado vaga o no contiene un hecho concreto,
  marca "usar": false.
- "hecho" debe explicar exactamente qué ocurrió.
- "contexto" debe contener 1 a 3 frases con detalles adicionales presentes
  en la MISMA evidencia.
- Si no existe contexto adicional real, usa contexto vacío.
- Conserva títulos propios, personajes, proyectos y nombres si aparecen
  en la evidencia.
- "apoyos" debe contener 1 a 3 fragmentos BREVES COPIADOS LITERALMENTE
  de la evidencia original. No traduzcas los apoyos.

Devuelve SOLO JSON válido:
{{
  "fichas": [
    {{
      "evidencia": 1,
      "usar": true,
      "hecho": "hecho concreto en español",
      "contexto": "contexto adicional en español",
      "apoyos": ["fragmento literal"]
    }}
  ]
}}

EVIDENCIAS:
{evidence_text}
"""

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": "30m",
                    "options": {
                        "temperature": 0.0,
                        "num_predict": 1200,
                        "num_ctx": 7168,
                    },
                },
                timeout=max(OLLAMA_TIMEOUT, 210),
            )

            response.raise_for_status()
            raw = response.json().get("response", "").strip()

            if not raw:
                return None

            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"\s*```$", "", raw)

            data = json.loads(raw)
            cards = data.get("fichas")

            if not isinstance(cards, list):
                return None

            valid_cards = []

            for card in cards:
                if not isinstance(card, dict):
                    continue

                if not card.get("usar", False):
                    continue

                try:
                    idx = int(card.get("evidencia", 0))
                except Exception:
                    continue

                if idx < 1 or idx > len(prepared):
                    continue

                fact = clean(str(card.get("hecho") or ""), 1400)
                context = clean(str(card.get("contexto") or ""), 2200)
                supports = card.get("apoyos", [])

                if not fact or not final_is_spanish(fact):
                    continue

                source = prepared[idx - 1]
                source_text = f"{source.title}. {source.context}"

                combined = fact
                if context:
                    combined += ". " + context

                if not output_supported_by_evidence(
                    combined,
                    source_text,
                    intent.topic,
                    supports=supports,
                ):
                    # Often the core event is supported but an extra context
                    # sentence overreaches. Try salvaging the supported event
                    # instead of throwing away the whole news item.
                    if output_supported_by_evidence(
                        fact,
                        source_text,
                        intent.topic,
                        supports=supports,
                    ):
                        print(
                            f"[OLLAMA] Ficha {idx}: contexto descartado; "
                            f"se conserva el hecho respaldado."
                        )
                        context = ""
                        combined = fact
                    else:
                        print(
                            f"[OLLAMA] Ficha {idx} descartada por falta de respaldo."
                        )
                        continue

                if not summary_specific_enough(combined, source_text):
                    print(
                        f"[OLLAMA] Ficha {idx} descartada por falta de especificidad."
                    )
                    continue

                valid_cards.append({
                    "evidencia": idx,
                    "hecho": fact,
                    "contexto": context,
                })

            return valid_cards or None

        except Exception as exc:
            print(f"[OLLAMA NORMALIZER] {exc}")
            return None

    def _write_final(
        self,
        intent: QueryIntent,
        cards: List[dict],
    ) -> Optional[str]:
        """
        Stage 2:
        Write the final user-facing answer from already-normalized Spanish facts.
        """
        card_text = json.dumps(cards, ensure_ascii=False, indent=2)

        prompt = f"""
Eres JARVIS.

Redacta la respuesta final para el usuario utilizando EXCLUSIVAMENTE las fichas
factuales en español que aparecen abajo.

PETICIÓN:
{intent.original}

TEMA:
{intent.topic}

OBJETIVO:
- Entrega hasta {intent.count} noticias distintas.
- Si existen {intent.count} fichas útiles, entrega {intent.count}.
- Cada noticia debe tener entre 2 y 4 oraciones cuando haya suficiente contexto.
- La primera oración explica claramente QUÉ ocurrió.
- Las siguientes aportan contexto real de la ficha.
- Debe sonar natural, lógico y completo.
- Todo debe estar EN ESPAÑOL.
- No escribas titulares sueltos.
- No escribas frases en inglés.
- No muestres fuentes, URLs, dominios, fechas técnicas ni metadatos.
- No añadas hechos que no estén en las fichas.
- No repitas la misma idea para ganar longitud.
- No inventes importancia ni consecuencias.
- Si una ficha solo permite 2 oraciones fiables, usa 2 y no rellenes.

Devuelve SOLO el texto final numerado:
1. ...
2. ...
3. ...

FICHAS:
{card_text}
"""

        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": "30m",
                    "options": {
                        "temperature": 0.05,
                        "num_predict": 1100,
                        "num_ctx": 6144,
                    },
                },
                timeout=max(OLLAMA_TIMEOUT, 210),
            )

            response.raise_for_status()
            answer = response.json().get("response", "").strip()

            if not final_answer_quality(answer, intent.count):
                print("[OLLAMA WRITER] Respuesta final rechazada por calidad.")
                return None

            return answer

        except Exception as exc:
            print(f"[OLLAMA WRITER] {exc}")
            return None

    def _cards_fallback(
        self,
        cards: List[dict],
        count: int,
    ) -> Optional[str]:
        """
        User-facing fallback built ONLY from already validated Spanish fact
        cards. Never exposes raw English headlines/snippets.
        """
        blocks = []

        for index, card in enumerate(cards[:count], 1):
            fact = clean(str(card.get("hecho") or ""), 1400)
            context = clean(str(card.get("contexto") or ""), 2200)

            if not fact or not final_is_spanish(fact):
                continue

            body = fact.rstrip(".")

            if context and final_is_spanish(context):
                # Avoid repeating the same sentence in different words.
                if context_adds_information(fact, context):
                    body += ". " + context.rstrip(".")

            blocks.append(f"{index}. {body}.")

        return "\\n\\n".join(blocks) if blocks else None

    def stream_compose(
        self,
        intent: QueryIntent,
        evidence: List[Evidence],
        budget: WorkBudget,
    ):
        if not evidence:
            return

        prepared = self._prepare_evidence(intent, evidence)[:budget.max_units]

        if not prepared:
            return

        effective_count = (
            1
            if intent.count <= 1
            else min(intent.count, len(prepared))
        )

        # One architecture, adaptive prompt budget.
        if intent.depth <= 1:
            chars_per_unit = 280
        elif intent.depth == 2:
            chars_per_unit = 380
        else:
            chars_per_unit = 500

        units = []

        for idx, item in enumerate(prepared, 1):
            ctx = sanitize_search_snippet(item.context) or item.context
            units.append(
                f"[{idx}] {clean(item.title, 220)} :: {clean(ctx, chars_per_unit)}"
            )

        relation_hint = {
            "identity": "Identifica a la persona y su actividad/relevancia principal.",
            "definition": "Define qué es y su función o naturaleza principal.",
            "author": "Da el autor o autora.",
            "director": "Da el director o directora.",
            "date": "Da la fecha solicitada.",
            "price": "Da el precio solicitado.",
        }.get(intent.relation, "")

        rules = [
            "Responde en español natural usando solo la evidencia.",
            "No inventes datos ni repitas ideas.",
            "No muestres fuentes ni URLs.",
        ]

        if relation_hint:
            rules.append(relation_hint)

        if intent.temporal_focus == "recent":
            rules.append("Prioriza acontecimientos recientes y concretos.")

        if intent.diversity == "high":
            rules.append(
                f"Entrega como máximo {effective_count} puntos distintos; un mismo hecho nunca cuenta dos veces."
            )

        if intent.novelty == "high":
            rules.append("Prioriza hechos menos obvios que estén realmente respaldados.")

        if effective_count <= 1:
            rules.append("Sé directo: normalmente 1-3 oraciones.")
        else:
            rules.append("Cada punto debe explicar qué ocurrió y añadir contexto útil sin relleno.")

        prompt = (
            f"PETICIÓN: {intent.original}\n"
            + "REGLAS:\n- "
            + "\n- ".join(rules)
            + "\nEVIDENCIA:\n"
            + "\n".join(units)
            + "\nRESPUESTA:"
        )

        if effective_count <= 1:
            num_predict = 110 if intent.depth <= 1 else 170
        else:
            num_predict = min(500, 80 + effective_count * 80)

        try:
            started = time.time()
            first_piece_at = None

            with requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": True,
                    "keep_alive": -1,
                    "options": {
                        "temperature": 0.0,
                        "num_predict": num_predict,
                        "num_ctx": OLLAMA_RUNNER_CTX,
                    },
                },
                stream=True,
                timeout=(5, 150),
            ) as response:
                response.raise_for_status()

                for raw_line in response.iter_lines(
                    decode_unicode=True,
                    chunk_size=1,
                ):
                    if not raw_line:
                        continue

                    try:
                        payload = json.loads(raw_line)
                    except Exception:
                        continue

                    piece = payload.get("response") or ""

                    if piece:
                        if first_piece_at is None:
                            first_piece_at = time.time()
                            print(
                                "[STREAM] "
                                f"first_token={int((first_piece_at-started)*1000)}ms "
                                f"depth={intent.depth} count={intent.count}"
                            )
                        yield piece

                    if payload.get("done"):
                        def ns_to_ms(value):
                            try:
                                return round(float(value) / 1_000_000, 1)
                            except Exception:
                                return 0.0

                        print(
                            "[STREAM DONE] "
                            f"total={int((time.time()-started)*1000)}ms "
                            f"load={ns_to_ms(payload.get('load_duration'))}ms "
                            f"prompt={ns_to_ms(payload.get('prompt_eval_duration'))}ms "
                            f"eval={ns_to_ms(payload.get('eval_duration'))}ms "
                            f"tokens={payload.get('eval_count', 0)} "
                            f"ctx={OLLAMA_RUNNER_CTX}"
                        )
                        break

        except Exception as exc:
            print(f"[STREAM COMPOSER] {exc}")
            return

    def compose(
        self,
        intent: QueryIntent,
        evidence: List[Evidence],
        budget: WorkBudget,
    ) -> Optional[str]:
        if not self.health() or not evidence:
            return None

        prepared = self._prepare_evidence(intent, evidence)[:budget.max_units]

        if not prepared:
            return None

        effective_count = (
            1
            if intent.count <= 1
            else min(intent.count, len(prepared))
        )

        unit_blocks = []
        per_unit = max(320, min(900, budget.max_context_chars // max(1, len(prepared)) + 250))

        for idx, item in enumerate(prepared, 1):
            context = sanitize_search_snippet(item.context) or item.context
            unit_blocks.append(
                f"[UNIDAD {idx}]\n"
                f"TITULO: {clean(item.title, 300)}\n"
                f"CONTEXTO: {clean(context, per_unit)}"
            )

        units_text = "\n\n".join(unit_blocks)

        relation_instruction = {
            "identity": "Identifica quién es y su actividad o relevancia principal.",
            "definition": "Define qué es y su naturaleza o función principal.",
            "author": "Responde quién es el autor o autora.",
            "director": "Responde quién dirige.",
            "date": "Responde la fecha solicitada.",
            "price": "Responde el precio solicitado.",
        }.get(intent.relation, "")

        prompt = f"""
Eres JARVIS.

PETICIÓN:
{intent.original}

PLAN:
objetivo={intent.goal}
relación={intent.relation or "ninguna"}
cantidad={effective_count}
temporalidad={intent.temporal_focus}
diversidad={intent.diversity}
profundidad={intent.depth}
tipo_unidad={intent.unit_type}

REGLAS:
- Usa EXCLUSIVAMENTE las unidades.
- Todo en español natural.
- Responde exactamente a la intención.
- {relation_instruction}
- Si temporalidad=recent, prioriza lo más reciente disponible.
- Si diversidad=high, cada punto debe representar una unidad/hecho distinto.
- Si cantidad>1, intenta entregar esa cantidad solo si existen unidades suficientes.
- Nunca dividas un mismo hecho en varios puntos para rellenar.
- No inventes nombres, fechas, cifras, consecuencias ni contexto.
- No muestres fuentes, URLs, dominios o metadatos.
- No uses relleno como "no se proporcionaron detalles", "generó gran interés",
  "revolucionó", "se espera que sea emocionante".
- Para una pregunta simple, responde directo y breve.
- Para una petición amplia, añade contexto real sin repetir ideas.

UNIDADES:
{units_text}

RESPUESTA:
"""

        try:
            started = time.time()

            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": -1,
                    "options": {
                        "temperature": 0.0,
                        "num_predict": min(850, max(140, effective_count * (150 if intent.depth >= 2 else 90))),
                        "num_ctx": OLLAMA_RUNNER_CTX,
                    },
                },
                timeout=max(OLLAMA_TIMEOUT, 180),
            )

            response.raise_for_status()
            answer = clean(response.json().get("response", "").strip(), 7000)

            if not answer:
                return None

            # One lightweight quality gate.
            if not final_is_spanish(answer):
                print("[QUALITY] idioma")
                return None

            if not user_facing_text_clean(answer):
                print("[QUALITY] basura web")
                return None

            source_text = " ".join(f"{x.title} {x.context}" for x in prepared)

            if not extract_numbers(answer).issubset(extract_numbers(source_text)):
                print("[QUALITY] cifra no respaldada")
                return None

            if not extract_years(answer).issubset(extract_years(source_text)):
                print("[QUALITY] año no respaldado")
                return None

            print(f"[COMPOSER] total={int((time.time()-started)*1000)}ms units={len(prepared)}")
            return answer

        except Exception as exc:
            print(f"[COMPOSER] {exc}")
            return None

    def stream_fact(
        self,
        intent: QueryIntent,
        evidence: List[Evidence],
    ):
        if not evidence:
            return
        relation = factual_relation_from_question(intent.original)
        prepared = self._prepare_evidence(intent, evidence)[:2]
        if not prepared:
            return
        snippets=[]
        for item in prepared:
            title=clean(item.title,180)
            context=compact_fact_context(item.context, relation, max_chars=260)
            if context: snippets.append(f"{title}: {context}")
        evidence_text="\n".join(snippets[:2])
        relation_instruction={
            "identity":"Identifica quién es la persona y su actividad principal. No hables de familiares salvo que sea imprescindible.",
            "definition":"Define qué es la entidad y su función principal. No inventes fundadores, fechas ni historia si no son necesarias.",
            "author":"Responde quién es el autor o autora de la obra.",
            "director":"Responde quién dirige la obra.",
            "date":"Responde la fecha solicitada.",
            "price":"Responde el precio solicitado.",
            "fact":"Responde exactamente el dato solicitado.",
        }.get(relation,"Responde exactamente el dato solicitado.")
        prompt=f"""Pregunta: {intent.original}
Evidencia:
{evidence_text}
Responde en español, 1-3 oraciones. {relation_instruction}
Usa solo la evidencia. No inventes. No muestres fuentes."""
        try:
            started=time.time()
            with requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": True,
                    "keep_alive": -1,
                    "options": {"temperature":0.0,"num_predict":100,"num_ctx":1024},
                },
                stream=True,
                timeout=(5,90),
            ) as response:
                response.raise_for_status()
                first_piece_at=None
                for raw_line in response.iter_lines(decode_unicode=True, chunk_size=1):
                    if not raw_line: continue
                    try: payload=json.loads(raw_line)
                    except Exception: continue
                    piece=payload.get("response") or ""
                    if piece:
                        if first_piece_at is None:
                            first_piece_at=time.time()
                            print(f"[STREAM TIMING] first_token={int((first_piece_at-started)*1000)}ms")
                        yield piece
                    if payload.get("done"):
                        total_ms=int((time.time()-started)*1000)
                        def ns_to_ms(value):
                            try: return round(float(value)/1_000_000,1)
                            except Exception: return 0.0
                        print("[OLLAMA STREAM TIMING] "
                              f"total={total_ms}ms "
                              f"load={ns_to_ms(payload.get('load_duration'))}ms "
                              f"prompt={ns_to_ms(payload.get('prompt_eval_duration'))}ms "
                              f"eval={ns_to_ms(payload.get('eval_duration'))}ms "
                              f"tokens={payload.get('eval_count',0)}")
                        break
        except Exception as exc:
            print(f"[OLLAMA STREAM FACT] {exc}")
            return

    def synthesize_fact(
        self,
        intent: QueryIntent,
        evidence: List[Evidence],
    ) -> Optional[str]:
        if not self.health() or not evidence:
            return None
        relation=factual_relation_from_question(intent.original)
        prepared=self._prepare_evidence(intent,evidence)[:2]
        if not prepared: return None
        snippets=[]
        for item in prepared:
            context=compact_fact_context(item.context, relation, 260)
            if context: snippets.append(f"{clean(item.title,180)}: {context}")
        evidence_text="\n".join(snippets[:2])
        prompt=(f"Pregunta: {intent.original}\nEvidencia:\n{evidence_text}\n"
                "Responde en español, directamente, en 1-3 oraciones. "
                "Usa solo la evidencia. No inventes ni muestres fuentes.")
        try:
            response=requests.post(OLLAMA_URL,json={
                "model":OLLAMA_MODEL,"prompt":prompt,"stream":False,"keep_alive":-1,
                "options":{"temperature":0.0,"num_predict":100,"num_ctx":1024},
            },timeout=max(OLLAMA_TIMEOUT,60))
            response.raise_for_status()
            answer=clean(response.json().get("response","").strip(),1400)
            if not answer or not final_is_spanish(answer) or not user_facing_text_clean(answer): return None
            return answer
        except Exception as exc:
            print(f"[OLLAMA FACT] {exc}")
            return None

    def synthesize(
        self,
        intent: QueryIntent,
        evidence: List[Evidence],
    ) -> Optional[str]:
        if not self.health() or not evidence:
            return None

        prepared = self._prepare_evidence(intent, evidence)

        if not prepared:
            return None

        cards = self._normalize_evidence(intent, prepared)

        if not cards:
            return None

        # Keep distinct cards only.
        distinct = []

        for card in cards:
            combined = f"{card['hecho']} {card.get('contexto', '')}"

            if any(
                similarity(combined, f"{old['hecho']} {old.get('contexto', '')}") >= 0.55
                for old in distinct
            ):
                continue

            distinct.append(card)

            if len(distinct) >= intent.count:
                break

        if not distinct:
            return None

        final_answer = self._write_final(intent, distinct)

        if final_answer:
            return final_answer

        print(
            "[OLLAMA WRITER] Se usa fallback de fichas factuales validadas."
        )
        return self._cards_fallback(distinct, intent.count)


# ============================================================
# RESPONSE
# ============================================================

class ResponseBuilder:
    def extractive(
        self,
        intent: QueryIntent,
        evidence: List[Evidence],
    ) -> str:
        """
        Safety fallback.
        For news, we do NOT expose raw English headlines/snippets anymore.
        If the synthesis layer fails, say so plainly rather than regress to
        crawler output.
        """
        if intent.is_news:
            return (
                "Encontré información reciente, pero la capa de redacción no "
                "consiguió convertirla en una respuesta completa y fiable en español. "
                "Prefiero no mostrar titulares crudos o fragmentos en inglés."
            )

        selected = []

        for item in evidence:
            context = sanitize_search_snippet(item.context)

            if not context:
                continue

            if not final_is_spanish(context):
                continue

            selected.append(context)

            if len(selected) >= intent.count:
                break

        if not selected:
            return (
                "Encontré información relacionada, pero no pasó el control "
                "de calidad necesario para responder con seguridad."
            )

        return "\n\n".join(
            f"{index}. {item}"
            for index, item in enumerate(selected, 1)
        )


# ============================================================
# SERVICE
# ============================================================

class InternetService:
    def __init__(self):
        self.parser = IntentParser()
        self.exec_planner = ExecutionPlanner()
        self.search_planner = SearchPlanner()
        self.search = SearXNGClient()
        self.ranker = ResultRanker()
        self.extractor = ArticleExtractor()
        self.evidence_builder = EvidenceBuilder()
        self.synth = OllamaSynthesizer()
        self.response = ResponseBuilder()
        self.clusterer = EventClusterer()
        self.selector = UnitSelector()
        self.temporal = TemporalValidityEngine()
        self.consensus = ClaimConsensusEngine()
        self.unit_limiter = HardUnitLimiter()

    def prepare(self, question: str) -> dict:
        started = time.time()

        t0 = time.time()
        intent = self.parser.parse(question)
        budget = self.exec_planner.budget(intent)
        queries = self.search_planner.build(intent, budget)
        understand_ms = int((time.time() - t0) * 1000)

        print(
            "[PLAN] "
            f"goal={intent.goal} relation={intent.relation or '-'} "
            f"count={intent.count} temporal={intent.temporal_focus} "
            f"depth={intent.depth} diversity={intent.diversity} "
            f"queries={len(queries)} articles={'on' if budget.fetch_articles else 'off'}"
        )

        t0 = time.time()
        raw_results = self.search.search(intent, queries)
        search_ms = int((time.time() - t0) * 1000)

        t0 = time.time()
        ranked_results = self.ranker.rank(raw_results, intent)[:budget.max_ranked]
        rank_ms = int((time.time() - t0) * 1000)

        t0 = time.time()
        articles = []

        if budget.fetch_articles:
            articles = self.extractor.extract_many(
                ranked_results[:budget.max_articles],
                intent,
            )

        articles_ms = int((time.time() - t0) * 1000)

        t0 = time.time()
        evidence = self.evidence_builder.build(articles, intent)

        generic_builder = GenericSearchEvidenceBuilder()

        if len(evidence) < budget.max_units:
            evidence.extend(
                generic_builder.build(
                    ranked_results,
                    intent,
                    evidence,
                    limit=budget.max_units,
                )
            )

        evidence = [x for x in evidence if evidence_specific_enough(x)]

        evidence = self.clusterer.unique_events(
            evidence,
            limit=max(budget.max_units * 2, budget.max_units + 3),
        )

        # Universal evidence refinement.
        evidence = self.temporal.apply(evidence, intent)
        evidence = self.consensus.apply(evidence, intent)
        evidence = self.unit_limiter.collapse(evidence, intent)

        evidence = self.selector.select(
            evidence,
            intent,
            limit=budget.max_units,
        )

        # Final collapse after selector in case ranking brought near-duplicates
        # back together.
        evidence = self.unit_limiter.collapse(evidence, intent)

        evidence_ms = int((time.time() - t0) * 1000)

        print(
            "[TIME] "
            f"understand={understand_ms}ms search={search_ms}ms rank={rank_ms}ms "
            f"articles={articles_ms}ms evidence={evidence_ms}ms units={len(evidence)} "
            f"answer_cap={self.unit_limiter.answer_limit(evidence, intent)}"
        )

        return {
            "started": started,
            "intent": intent,
            "budget": budget,
            "raw_results": raw_results,
            "ranked_results": ranked_results,
            "articles": articles,
            "evidence": evidence,
            "timing": {
                "understand_ms": understand_ms,
                "search_ms": search_ms,
                "rank_ms": rank_ms,
                "articles_ms": articles_ms,
                "evidence_ms": evidence_ms,
            },
        }

    def answer_prepared(self, prepared: dict) -> dict:
        intent = prepared["intent"]
        budget = prepared["budget"]
        evidence = prepared["evidence"]

        t0 = time.time()
        answer = self.synth.compose(intent, evidence, budget) if evidence else None
        compose_ms = int((time.time() - t0) * 1000)

        if not answer:
            answer = self.response.extractive(intent, evidence)

        timing = dict(prepared["timing"])
        timing["compose_ms"] = compose_ms
        total_ms = int((time.time() - prepared["started"]) * 1000)

        print(f"[TIME] compose={compose_ms}ms total={total_ms}ms")

        return {
            "respuesta": answer,
            "fuentes": [
                {
                    "titulo": item.title,
                    "url": item.url,
                    "publishedDate": item.published_date,
                    "score": round(item.score, 2),
                }
                for item in evidence[:8]
            ],
            "meta": {
                "tema": intent.topic,
                "goal": intent.goal,
                "relation": intent.relation,
                "cantidad": intent.count,
                "temporal_focus": intent.temporal_focus,
                "diversity": intent.diversity,
                "depth": intent.depth,
                "unit_type": intent.unit_type,
                "eventos_unicos": len(evidence),
                "answer_cap": self.unit_limiter.answer_limit(evidence, intent),
                "evidencias": len(evidence),
                "resultados_crudos": len(prepared["raw_results"]),
                "resultados_filtrados": len(prepared["ranked_results"]),
                "articulos_extraidos": len(prepared["articles"]),
                "timing": timing,
                "tiempo_ms": total_ms,
                "version": "7.4",
            },
        }

    def answer(self, question: str) -> dict:
        return self.answer_prepared(self.prepare(question))


service = InternetService()


# ============================================================
# ENDPOINTS
# ============================================================

@app.route("/internet", methods=["POST"])
def internet():
    data = request.get_json(silent=True) or {}
    question = (data.get("pregunta") or "").strip()

    if not question:
        return jsonify({
            "respuesta": "No recibí ninguna pregunta.",
            "fuentes": [],
            "meta": {},
        })

    try:
        return jsonify(service.answer(question))

    except Exception as exc:
        print(traceback.format_exc())

        return jsonify({
            "respuesta": "No pude completar la búsqueda en internet.",
            "fuentes": [],
            "meta": {"error": str(exc)},
        }), 500


@app.route("/internet_stream", methods=["POST"])
def internet_stream():
    data = request.get_json(silent=True) or {}
    question = (data.get("pregunta") or "").strip()

    def generate():
        if not question:
            yield json.dumps(
                {"piece": "No recibí ninguna pregunta."},
                ensure_ascii=False,
            ) + "\n"
            return

        try:
            prepared = service.prepare(question)
            intent = prepared["intent"]
            budget = prepared["budget"]
            evidence = prepared["evidence"]

            if not evidence:
                result = service.answer_prepared(prepared)
                yield json.dumps(
                    {"piece": result["respuesta"]},
                    ensure_ascii=False,
                ) + "\n"
                return

            streamed_any = False

            for piece in service.synth.stream_compose(
                intent,
                evidence,
                budget,
            ):
                if not piece:
                    continue

                streamed_any = True
                yield json.dumps(
                    {"piece": piece},
                    ensure_ascii=False,
                ) + "\n"

            if streamed_any:
                return

            # Fallback only if the streaming LLM path failed entirely.
            result = service.answer_prepared(prepared)
            yield json.dumps(
                {"piece": result["respuesta"]},
                ensure_ascii=False,
            ) + "\n"

        except Exception:
            print(traceback.format_exc())
            yield json.dumps(
                {"piece": "No pude completar la búsqueda en internet."},
                ensure_ascii=False,
            ) + "\n"

    return Response(
        generate(),
        mimetype="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/status")
def status():
    searx_ok = service.search.health()
    ollama_ok = service.synth.health()

    return jsonify({
        "ok": searx_ok,
        "searxng": searx_ok,
        "ollama": ollama_ok,
        "modelo": OLLAMA_MODEL,
        "arquitectura": "Jarvis Internet Engine v7.4",
        "modo": (
            "search discovery + article extraction + coherent evidence + "
            "validated Spanish synthesis + optional deep reasoning"
        ),
    })


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    warm_ollama_model()
    print("")
    print("====================================================")
    print("          JARVIS INTERNET ENGINE v7.4")
    print("====================================================")
    print("SearXNG   : http://127.0.0.1:8888")
    print("API       : http://127.0.0.1:5000")
    print("Extractor : estructural + JSON-LD + parrafos reales")
    print("Evidence  : snippets rápidos para hechos + artículos para investigación")
    print(f"LLM       : compositor universal + runner fijo ctx={OLLAMA_RUNNER_CTX}")
    print("Temporal  : current/recent validity + stale-event rejection")
    print("Consensus : hard-fact corroboration + hard unit limit")
    print("Freshness : 30 dias; ranking propio, sin depender de time_range")
    print("====================================================")
    print("")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        threaded=True,
    )
