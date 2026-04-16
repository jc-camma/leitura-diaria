from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from html import unescape
from urllib.parse import urlencode
from urllib.request import urlopen

from app.models import Lesson

logger = logging.getLogger(__name__)

_PREFERRED_CHANNEL_HANDLES = [
    "sejaumapessoamelhor",
    "arataacademy",
    "superresumosaudiobooks",
    "acarolalvarenga",
    "profdiogomoreira",
]
_PREFERRED_CHANNEL_PRIORITY = {handle: idx for idx, handle in enumerate(_PREFERRED_CHANNEL_HANDLES)}


@dataclass(frozen=True)
class YoutubeVideoReference:
    title: str
    url: str
    source: str  # "api" or "search"


def find_most_relevant_video(
    lesson: Lesson,
    youtube_api_key: str | None = None,
    timeout_seconds: float = 8.0,
) -> YoutubeVideoReference:
    query = _build_query(lesson)
    fallback = _search_fallback(query)
    if not youtube_api_key:
        return fallback
    required_tokens = _required_title_tokens(lesson)
    prioritized = _find_prioritized_video_from_search_page(
        fallback,
        required_tokens=required_tokens,
        timeout_seconds=timeout_seconds,
    )
    if prioritized is not None:
        return prioritized
    return fallback


def _build_query(lesson: Lesson) -> str:
    return f"{lesson.title} {lesson.author} resumo"


def _required_title_tokens(lesson: Lesson) -> set[str]:
    title_tokens = _extract_significant_tokens(lesson.title)
    if title_tokens:
        return set(title_tokens)
    author_tokens = _extract_significant_tokens(lesson.author)
    return set(author_tokens)


def _normalize_text(text: str) -> str:
    lowered = unescape(text or "").lower().strip()
    normalized = unicodedata.normalize("NFKD", lowered).encode("ascii", "ignore").decode("ascii")
    return normalized


def _tokenize(text: str) -> list[str]:
    normalized = _normalize_text(text)
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return [t for t in tokens if t]


def _extract_significant_tokens(text: str) -> list[str]:
    stopwords = {
        "a",
        "as",
        "o",
        "os",
        "um",
        "uma",
        "de",
        "do",
        "da",
        "dos",
        "das",
        "e",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "para",
        "por",
        "com",
        "sem",
        "ao",
        "aos",
        "sobre",
        "resumo",
        "resenha",
    }
    ordered: list[str] = []
    seen: set[str] = set()
    for token in _tokenize(text):
        if token in stopwords:
            continue
        if token.isdigit():
            if len(token) < 2:
                continue
        elif len(token) < 3:
            continue
        if token in seen:
            continue
        ordered.append(token)
        seen.add(token)
    return ordered


def _title_match_score(required_tokens: set[str], video_title: str) -> int:
    if not required_tokens:
        return 0
    title_tokens = set(_tokenize(video_title))
    score = 0
    for token in required_tokens:
        if token not in title_tokens:
            continue
        if token.isdigit():
            score += 5
        elif len(token) >= 7:
            score += 3
        elif len(token) >= 5:
            score += 2
        else:
            score += 1
    return score


def _search_fallback(query: str) -> YoutubeVideoReference:
    search_url = f"https://www.youtube.com/results?{urlencode({'search_query': query})}"
    return YoutubeVideoReference(
        title=f"Buscar no YouTube: {query}",
        url=search_url,
        source="search",
    )


def _find_prioritized_video_from_search_page(
    fallback: YoutubeVideoReference,
    required_tokens: set[str],
    timeout_seconds: float,
) -> YoutubeVideoReference | None:
    try:
        with urlopen(fallback.url, timeout=timeout_seconds) as response:  # nosec: B310
            html = response.read().decode("utf-8", errors="ignore")
        payload = _extract_yt_initial_data(html)
        if payload is None:
            return None

        best_by_priority: dict[int, tuple[int, int, str, str]] = {}
        for video in _iter_video_renderers(payload):
            channel_handle = _extract_channel_handle(video)
            priority = _preferred_priority(channel_handle)
            if priority is None:
                continue
            video_id = (video.get("videoId") or "").strip()
            if not video_id:
                continue
            title = _extract_title(video)
            score = _title_match_score(required_tokens, title)
            if required_tokens and score <= 0:
                continue
            views = _extract_view_count(video)
            current = best_by_priority.get(priority)
            if current is None or score > current[0] or (score == current[0] and views > current[1]):
                best_by_priority[priority] = (score, views, video_id, title)
        if not best_by_priority:
            return None

        best_priority = min(best_by_priority)
        _, _, best_id, best_title = best_by_priority[best_priority]
        return YoutubeVideoReference(
            title=best_title or "Video recomendado no YouTube",
            url=f"https://www.youtube.com/watch?v={best_id}",
            source="search",
        )
    except Exception as exc:
        logger.warning("Falha ao extrair video priorizado da busca do YouTube: %s", exc)
        return None


def _extract_yt_initial_data(html: str) -> dict | None:
    marker = "var ytInitialData = "
    idx = html.find(marker)
    if idx == -1:
        marker = "ytInitialData = "
        idx = html.find(marker)
    if idx == -1:
        return None

    start = html.find("{", idx)
    if start == -1:
        return None

    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(html[start:])
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _iter_video_renderers(payload: object):
    if isinstance(payload, dict):
        renderer = payload.get("videoRenderer")
        if isinstance(renderer, dict):
            yield renderer
        for value in payload.values():
            yield from _iter_video_renderers(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_video_renderers(item)


def _extract_title(video_renderer: dict) -> str:
    title_obj = video_renderer.get("title") or {}
    simple = (title_obj.get("simpleText") or "").strip()
    if simple:
        return unescape(simple)
    runs = title_obj.get("runs") or []
    parts = [str(run.get("text") or "").strip() for run in runs if isinstance(run, dict)]
    return unescape("".join(parts)).strip()


def _extract_view_count(video_renderer: dict) -> int:
    text_obj = video_renderer.get("viewCountText") or {}
    text = str(text_obj.get("simpleText") or "").strip()
    if not text:
        runs = text_obj.get("runs") or []
        text = "".join(str(run.get("text") or "") for run in runs if isinstance(run, dict)).strip()
    return _parse_view_count_text(text)


def _extract_channel_handle(video_renderer: dict) -> str | None:
    owner_candidates = [
        video_renderer.get("ownerText") or {},
        video_renderer.get("longBylineText") or {},
        video_renderer.get("shortBylineText") or {},
    ]
    for owner in owner_candidates:
        runs = owner.get("runs") or []
        for run in runs:
            if not isinstance(run, dict):
                continue
            direct_text = _normalize_channel_handle(str(run.get("text") or ""))
            if direct_text:
                return direct_text
            endpoint = run.get("navigationEndpoint") or {}
            browse = endpoint.get("browseEndpoint") or {}
            url = str(browse.get("canonicalBaseUrl") or "")
            from_url = _normalize_channel_handle(url)
            if from_url:
                return from_url
            web_meta = ((endpoint.get("commandMetadata") or {}).get("webCommandMetadata") or {})
            web_url = str(web_meta.get("url") or "")
            from_web_url = _normalize_channel_handle(web_url)
            if from_web_url:
                return from_web_url
    return None


def _normalize_channel_handle(raw: str) -> str | None:
    text = unescape(raw or "").strip().lower()
    if not text:
        return None
    if "/@" in text:
        text = text.split("/@", 1)[1]
    elif text.startswith("@"):
        text = text[1:]
    else:
        return None
    handle = re.split(r"[^a-z0-9._-]", text, maxsplit=1)[0]
    return handle or None


def _preferred_priority(handle: str | None) -> int | None:
    if not handle:
        return None
    return _PREFERRED_CHANNEL_PRIORITY.get(handle.lower())


def _parse_view_count_text(text: str) -> int:
    if not text:
        return 0
    normalized = _normalize_text(text)
    normalized = (
        normalized.replace("\xa0", " ")
        .replace("visualizacoes", "")
        .replace("visualizacao", "")
        .replace("views", "")
        .replace("view", "")
        .strip()
    )

    match = re.search(r"(\d[\d\.,]*)", normalized)
    if not match:
        return 0

    raw_number = match.group(1)

    number = _parse_decimal_number(raw_number)
    tokens = re.findall(r"[a-z]+", normalized)
    multiplier = 1
    if any(token.startswith("bilh") or token == "bi" for token in tokens):
        multiplier = 1_000_000_000
    elif any(token.startswith("milh") or token == "mi" for token in tokens):
        multiplier = 1_000_000
    elif "mil" in tokens:
        multiplier = 1_000
    return int(number * multiplier)


def _parse_decimal_number(raw_number: str) -> float:
    value = raw_number.strip()
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(".", "").replace(",", ".")
    elif "." in value:
        parts = value.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[-1]) == 3):
            value = "".join(parts)
    try:
        return float(value)
    except ValueError:
        return 0.0
