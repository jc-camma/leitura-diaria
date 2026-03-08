from __future__ import annotations

import re
from dataclasses import replace

from app.lesson import Lesson
from app.utils import extract_numbered_content, first_word, normalize_whitespace


_BANNED_REPHRASE: dict[str, str] = {
    "no contexto de": "ao analisar",
    "de forma passiva": "passivamente",
    "em ambientes acelerados": "em cenarios de alta pressao",
    "esse formato acelera aprendizado": "esse desenho acelera o aprendizado",
    "ao final, o objetivo": "no fechamento, o objetivo",
}

_OPENING_VARIANTS = [
    "Na pratica",
    "Em termos concretos",
    "Do ponto de vista aplicado",
    "No dia a dia",
    "Como resultado",
    "Para fechar",
]


def refine_lesson_local(lesson: Lesson) -> Lesson:
    central = _tighten(_replace_banned(lesson.central_idea))
    guided = _refine_guided_reading(lesson.guided_reading)
    concepts = _refine_concepts(lesson.concepts)
    practical = _refine_practical_applications(lesson.practical_applications)
    reflection = _tighten(_replace_banned(lesson.reflection_question))
    quote = _tighten(lesson.optional_quote) if lesson.optional_quote else None

    return replace(
        lesson,
        central_idea=central,
        guided_reading=guided,
        concepts=concepts,
        practical_applications=practical,
        reflection_question=reflection,
        optional_quote=quote,
    )


def _refine_concepts(concepts: list[str]) -> list[str]:
    ideas = [extract_numbered_content(item) for item in concepts if item.strip()]
    while len(ideas) < 1:
        ideas.append(f"Conceito essencial {len(ideas) + 1}")
    return [f"{idx}. {_tighten(_replace_banned(idea))}" for idx, idea in enumerate(ideas, start=1)]


def _refine_practical_applications(applications: list[str]) -> list[str]:
    raw = [extract_numbered_content(item) for item in applications if item.strip()]
    while len(raw) < 3:
        raw.append(f"Ponto de leitura complementar {len(raw) + 1}")
    raw = raw[:3]

    refined: list[str] = []
    for idx, item in enumerate(raw, start=1):
        text = _tighten(_replace_banned(item))
        refined.append(f"{idx}. {text}")
    return refined


def _refine_guided_reading(paragraphs: list[str]) -> list[str]:
    refined = [_tighten(_replace_banned(paragraph)) for paragraph in paragraphs if paragraph.strip()]
    return _vary_openings(refined)


def _vary_openings(paragraphs: list[str]) -> list[str]:
    if not paragraphs:
        return paragraphs
    seen: dict[str, int] = {}
    result: list[str] = []
    variant_idx = 0
    for paragraph in paragraphs:
        word = first_word(paragraph)
        seen[word] = seen.get(word, 0) + 1
        if word and seen[word] > 1:
            variant = _OPENING_VARIANTS[variant_idx % len(_OPENING_VARIANTS)]
            variant_idx += 1
            paragraph = _prepend_transition(paragraph, variant)
        result.append(paragraph)
    return result


def _prepend_transition(paragraph: str, prefix: str) -> str:
    if not paragraph:
        return paragraph
    lowered = paragraph[0].lower() + paragraph[1:] if len(paragraph) > 1 else paragraph.lower()
    return f"{prefix}, {lowered}"


def _replace_banned(text: str) -> str:
    if not text:
        return text
    updated = text
    for source, target in _BANNED_REPHRASE.items():
        updated = re.sub(re.escape(source), target, updated, flags=re.IGNORECASE)
    return updated


def _tighten(text: str) -> str:
    if not text:
        return text
    updated = normalize_whitespace(text)
    updated = re.sub(r"\b(como um sistema de escolhas diarias:)\b", "como sistema analitico:", updated)
    updated = re.sub(r"\b(nao e apenas)\b", "nao basta", updated, flags=re.IGNORECASE)
    updated = re.sub(r"\b(vai)\b", "ira", updated, flags=re.IGNORECASE)
    updated = re.sub(r"\s+([,.;:!?])", r"\1", updated)
    return updated.strip()
