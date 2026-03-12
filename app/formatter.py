from __future__ import annotations

import re
from dataclasses import replace

from app.lesson import Lesson
from app.utils import extract_numbered_content, normalize_whitespace, strip_concept_prefix


SECTION_ORDER: list[tuple[int, str]] = [
    (1, "Título"),
    (2, "Autor"),
    (3, "Tema"),
    (4, "Ideia central"),
    (5, "Conceitos fundamentais"),
    (6, "Leitura guiada"),
    (7, "3 aplicações práticas"),
    (8, "1 pergunta de reflexão"),
    (9, "Citação curta"),
    (10, "Vídeo recomendado no YouTube"),
]


def lesson_to_refinement_text(lesson: Lesson) -> str:
    concepts = "\n".join(_normalize_numbered_items(lesson.concepts, expected=None, prefix="Conceito"))
    guided = "\n\n".join([normalize_whitespace(p) for p in lesson.guided_reading if p.strip()])
    practical = "\n".join(
        _normalize_numbered_items(lesson.practical_applications, 3, "Aplicação prática")
    )
    quote = lesson.optional_quote.strip() if lesson.optional_quote else "-"

    return (
        "1. Título\n"
        f"{lesson.title}\n\n"
        "2. Autor\n"
        f"{lesson.author}\n\n"
        "3. Tema\n"
        f"{lesson.theme}\n\n"
        "4. Ideia central\n"
        f"{normalize_whitespace(lesson.central_idea)}\n\n"
        "5. Conceitos fundamentais\n"
        f"{concepts}\n\n"
        "6. Leitura guiada\n"
        f"{guided}\n\n"
        "7. 3 aplicações práticas\n"
        f"{practical}\n\n"
        "8. 1 pergunta de reflexão\n"
        f"{normalize_whitespace(lesson.reflection_question)}\n\n"
        "9. Citação curta\n"
        f"{quote}\n\n"
        "10. Vídeo recomendado no YouTube\n"
        "-\n"
    )


def lesson_from_refinement_text(base: Lesson, refined_text: str) -> Lesson | None:
    sections = _parse_sections(refined_text)
    if not sections:
        return None

    title = _single_line(sections.get(1), base.title)
    author = _single_line(sections.get(2), base.author)
    theme = _single_line(sections.get(3), base.theme)
    central_idea = _fallback(sections.get(4), base.central_idea)
    concepts = _parse_numbered_items(sections.get(5, ""), expected=None, prefix="Conceito")
    guided_reading = _parse_paragraphs(sections.get(6, ""))
    practical = _parse_numbered_items(
        sections.get(7, ""),
        expected=3,
        prefix="Aplicação prática",
    )
    reflection = _fallback(sections.get(8), base.reflection_question)
    quote_raw = _single_line(sections.get(9), base.optional_quote or "-")
    optional_quote = None if quote_raw.strip() in {"", "-", "—"} else quote_raw.strip()

    return normalize_lesson_lists(
        replace(
            base,
            title=title,
            author=author,
            theme=theme,
            central_idea=normalize_whitespace(central_idea),
            concepts=concepts,
            practical_applications=practical,
            reflection_question=normalize_whitespace(reflection),
            guided_reading=guided_reading or base.guided_reading,
            optional_quote=optional_quote,
        )
    )


def normalize_lesson_lists(lesson: Lesson) -> Lesson:
    concepts = _normalize_numbered_items(lesson.concepts, expected=None, prefix="Conceito")
    practical = _normalize_numbered_items(lesson.practical_applications, 3, "Aplicação prática")
    guided = [_strip_bullet_prefix(normalize_whitespace(p)) for p in lesson.guided_reading if p.strip()]
    guided = guided or lesson.guided_reading
    return replace(
        lesson,
        concepts=concepts,
        practical_applications=practical,
        guided_reading=guided,
    )


def _parse_sections(text: str) -> dict[int, str]:
    section_name_pattern = "|".join(re.escape(name) for _, name in SECTION_ORDER)
    pattern = re.compile(rf"(?mi)^\s*(\d{{1,2}})\.\s+(?:{section_name_pattern})\s*$")
    matches = list(pattern.finditer(text))
    if not matches:
        return {}
    sections: dict[int, str] = {}
    for idx, match in enumerate(matches):
        sec = int(match.group(1))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections[sec] = text[start:end].strip()
    return sections


def _single_line(value: str | None, default: str) -> str:
    if not value:
        return default
    first = value.strip().splitlines()[0].strip()
    return first or default


def _fallback(value: str | None, default: str) -> str:
    if not value:
        return default
    cleaned = normalize_whitespace(value)
    return cleaned or default


def _parse_numbered_items(section_text: str, expected: int | None, prefix: str) -> list[str]:
    lines = [line.strip() for line in section_text.splitlines() if line.strip()]
    cleaned = [extract_numbered_content(line) for line in lines]
    if prefix.lower().startswith("conceito"):
        cleaned = [strip_concept_prefix(item) for item in cleaned]
    cleaned = [line for line in cleaned if line]
    if expected is not None:
        while len(cleaned) < expected:
            cleaned.append(f"{prefix} {len(cleaned) + 1}")
        cleaned = cleaned[:expected]
    return [f"{idx}. {item}" for idx, item in enumerate(cleaned, start=1)]


def _normalize_numbered_items(items: list[str], expected: int | None, prefix: str) -> list[str]:
    values = [extract_numbered_content(item) for item in items if item.strip()]
    if prefix.lower().startswith("conceito"):
        values = [strip_concept_prefix(item) for item in values]
    if expected is not None:
        while len(values) < expected:
            values.append(f"{prefix} {len(values) + 1}")
        values = values[:expected]
    return [f"{idx}. {value}" for idx, value in enumerate(values, start=1)]


def _parse_paragraphs(section_text: str) -> list[str]:
    cleaned = normalize_whitespace(section_text)
    if not cleaned:
        return []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", cleaned) if part.strip()]
    return [_strip_bullet_prefix(paragraph) for paragraph in paragraphs]


def _strip_bullet_prefix(text: str) -> str:
    return re.sub(r"^\s*[-•]\s*", "", text).strip()
