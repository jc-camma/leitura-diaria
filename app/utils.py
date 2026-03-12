from __future__ import annotations

import re
import unicodedata


def normalize_whitespace(text: str) -> str:
    collapsed = re.sub(r"[ \t]+", " ", text)
    collapsed = re.sub(r"\s+\n", "\n", collapsed)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def first_word(text: str) -> str:
    match = re.search(r"[A-Za-zÀ-ÿ]+", text.strip())
    return (match.group(0) if match else "").lower()


def split_paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]


def normalize_for_similarity(text: str) -> str:
    lowered = text.lower()
    normalized = unicodedata.normalize("NFKD", lowered).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"\d+", " ", normalized)
    normalized = re.sub(r"[^a-z\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def extract_numbered_content(text: str) -> str:
    return re.sub(r"^\s*\d+\s*[\.\)\-:]*\s*", "", text).strip()


def strip_concept_prefix(text: str) -> str:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return ""
    cleaned = re.sub(r"^\s*(?:[-•*]\s*)+", "", cleaned)
    cleaned = re.sub(
        r"(?i)^\s*conceito(?:s)?(?:\s*\d+)?\s*[:\\-–—]\s*",
        "",
        cleaned,
    )
    return cleaned.strip()
