from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

from app.formatter import lesson_to_refinement_text, normalize_lesson_lists
from app.generator import generate_draft
from app.lesson import BookEntry, Lesson
from app.openai_refiner import generate_book_summary_with_openai
from app.quality import evaluate_lesson_quality
from app.refiner import refine_lesson_local
from app.utils import extract_numbered_content, normalize_whitespace, strip_concept_prefix
from app.youtube import find_most_relevant_video

logger = logging.getLogger(__name__)

_SECTION_NAMES = {
    1: "Ideia central",
    2: "Por que este livro importa",
    3: "Conceitos fundamentais do livro",
    4: "Modelo mental ou estrutura apresentada pelo autor",
    5: "Exemplo ou historia marcante do livro",
    6: "Aplicacao pratica",
    7: "Limitacoes ou criticas possiveis",
    8: "Sintese final",
}


def build_refined_lesson(entry: BookEntry, openai_api_key: str | None, openai_model: str) -> Lesson:
    draft = generate_draft(entry)
    locally_refined = normalize_lesson_lists(refine_lesson_local(draft))
    candidate = locally_refined

    if openai_api_key:
        generated_summary = generate_book_summary_with_openai(
            entry,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
        )
        if not generated_summary:
            raise RuntimeError("Falha ao gerar resumo com IA. Verifique OPENAI_API_KEY e conectividade.")
        parsed = _lesson_from_ai_summary_text(entry, generated_summary)
        if parsed is None:
            raise RuntimeError("Resumo IA retornou em formato invalido para o parser de secoes.")
        candidate = normalize_lesson_lists(parsed)

    report = evaluate_lesson_quality(candidate)
    if report.has_blocking_errors:
        if openai_api_key:
            raise RuntimeError("Resumo IA nao passou nas validacoes minimas de qualidade.")
        logger.warning("Qualidade bloqueante detectada; mantendo versao local.")
        return locally_refined
    min_words = min(900, locally_refined.word_count())
    if candidate.word_count() < min_words:
        if openai_api_key:
            raise RuntimeError(
                f"Resumo IA ficou curto demais ({candidate.word_count()} palavras). Minimo esperado: {min_words}."
            )
        logger.warning("Resumo IA ficou curto demais; mantendo versao local.")
        return locally_refined
    if candidate.word_count() > 1600:
        if openai_api_key:
            raise RuntimeError(f"Resumo IA excedeu 1600 palavras ({candidate.word_count()}).")
        logger.warning("Resumo IA excedeu 1600 palavras; mantendo versao local.")
        return locally_refined
    return candidate


def refinement_smoke_test(entry: BookEntry, openai_api_key: str | None, openai_model: str) -> Lesson:
    draft = generate_draft(entry)
    locally_refined = normalize_lesson_lists(refine_lesson_local(draft))
    refined = build_refined_lesson(entry, openai_api_key=openai_api_key, openai_model=openai_model)
    print(f"Before length: {len(lesson_to_refinement_text(locally_refined))}")
    print(f"After length: {len(lesson_to_refinement_text(refined))}")
    return refined


def resolve_youtube_reference(lesson: Lesson, youtube_api_key: str | None) -> tuple[str, str]:
    ref = find_most_relevant_video(lesson, youtube_api_key=youtube_api_key)
    return ref.url, ref.title


def today() -> date:
    return date.today()


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _lesson_from_ai_summary_text(entry: BookEntry, text: str) -> Lesson | None:
    sections = _parse_numbered_sections(text)
    if not sections:
        return None

    central = normalize_whitespace(sections.get(1, ""))
    if not central:
        return None

    section3_text = sections.get(3, "")
    concept_blocks = _extract_concept_blocks(section3_text)
    concept_names = _extract_concept_names(section3_text, entry.key_ideas, concept_blocks)
    concepts = [f"{idx}. {name}" for idx, name in enumerate(concept_names, start=1)]

    section6_text = sections.get(6, "")
    actions = _extract_practical_actions(section6_text, entry.practical_applications)
    practical = [f"{idx}. {item}" for idx, item in enumerate(actions, start=1)]

    guided: list[str] = []
    for sec in [2]:
        body = normalize_whitespace(sections.get(sec, ""))
        if body:
            guided.append(_strip_leading_quoted_title(body, entry.title))

    section3_guided = _format_concepts_guided_section(section3_text, concept_blocks, concept_names)
    guided.extend(section3_guided)

    for sec in [4, 5]:
        body = normalize_whitespace(sections.get(sec, ""))
        if body:
            guided.append(f"{sec}. {_SECTION_NAMES[sec]}\n{body}")

    section6_guided = _format_practical_guided_section(section6_text, actions)
    guided.extend(section6_guided)

    for sec in [7, 8]:
        body = normalize_whitespace(sections.get(sec, ""))
        if body:
            guided.append(f"{sec}. {_SECTION_NAMES[sec]}\n{body}")

    if not guided:
        return None

    synthesis_sentence = _first_sentence(sections.get(8, ""))
    first_concept = extract_numbered_content(concepts[0]) if concepts else "Conceito central"
    summary_bullets = [
        f"Tese central: {_first_sentence(central)}",
        f"Eixo conceitual dominante: {first_concept}.",
        f"Sintese final: {synthesis_sentence}",
    ]

    return Lesson(
        day=entry.day,
        title=entry.title,
        author=entry.author,
        theme=entry.theme,
        central_idea=central,
        concepts=concepts,
        practical_applications=practical,
        reflection_question=entry.reflection_question.strip(),
        guided_reading=guided,
        summary_bullets=summary_bullets,
        optional_quote=entry.optional_quote.strip() if entry.optional_quote else None,
    )


def _parse_numbered_sections(text: str) -> dict[int, str]:
    pattern = re.compile(
        r"(?mi)^\s*(?:#{1,6}\s*)?(?:\*\*)?([1-8])\.\s+"
        r"(ideia central|por que este livro importa|conceitos fundamentais do livro|"
        r"modelo mental ou estrutura apresentada pelo autor|exemplo ou hist[oó]ria marcante do livro|"
        r"aplica[cç][aã]o pr[aá]tica|limita[cç][oõ]es ou cr[ií]ticas poss[ií]veis|s[ií]ntese final)"
        r"\s*(?:\*\*)?\s*$"
    )
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


def _extract_concept_blocks(section_text: str) -> list[tuple[str, str, str]]:
    blocks: list[tuple[str, str, str]] = []
    starts = list(re.finditer(r"(?is)conceito\s*:\s*", section_text))
    for idx, match in enumerate(starts):
        start = match.end()
        end = starts[idx + 1].start() if idx + 1 < len(starts) else len(section_text)
        chunk = section_text[start:end]

        explanation_match = re.search(r"(?is)explica(?:cao|ção)\s*:\s*", chunk)
        example_match = re.search(r"(?is)exemplo\s*:\s*", chunk)
        if not explanation_match or not example_match:
            continue
        if explanation_match.start() >= example_match.start():
            continue

        name = _clean_inline_markup(chunk[:explanation_match.start()])
        explanation = _clean_inline_markup(chunk[explanation_match.end() : example_match.start()])
        example = _clean_inline_markup(chunk[example_match.end() :])
        if name:
            blocks.append((name, explanation, example))
    return blocks


def _extract_concept_names(
    section_text: str,
    fallback: list[str],
    concept_blocks: list[tuple[str, str, str]] | None = None,
) -> list[str]:
    names: list[str] = []
    if concept_blocks:
        names.extend([name for name, _, _ in concept_blocks if name])

    seen_lower = {item.lower() for item in names}

    candidates = [
        normalize_whitespace(
            re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line)
        )
        for line in section_text.splitlines()
        if line.strip()
    ]
    for line in candidates:
        lowered = line.lower()
        if lowered.startswith("explicacao:") or lowered.startswith("explicação:"):
            continue
        if lowered.startswith("exemplo:"):
            continue
        if lowered.startswith("conceitos fundamentais"):
            continue
        cleaned = strip_concept_prefix(
            _clean_inline_markup(
                re.sub(r"^\s*(?:[-*•]\s*)+", "", line).strip()
            )
        )
        if cleaned and cleaned.lower() not in seen_lower and len(cleaned.split()) <= 14:
            names.append(cleaned)
            seen_lower.add(cleaned.lower())

    fallback_clean = [normalize_whitespace(item) for item in fallback if item.strip()]
    if not names:
        names.extend(fallback_clean)
    if not names:
        names.append("Conceito essencial 1")
    return names


def _extract_practical_actions(section_text: str, fallback: list[str]) -> list[str]:
    items: list[str] = []
    numbered_blocks = re.findall(
        r"(?ms)^\s*(?:\d+[.)]|[-*])\s+(.+?)(?=^\s*(?:\d+[.)]|[-*])\s+|\Z)",
        section_text,
    )
    for block in numbered_blocks:
        cleaned = _clean_inline_markup(block)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered.startswith("aplicacao pratica") or lowered.startswith("aplicação prática"):
            continue
        if len(cleaned.split()) < 3:
            continue
        items.append(cleaned)

    if not items:
        lines = [normalize_whitespace(line) for line in section_text.splitlines() if line.strip()]
        for line in lines:
            cleaned = _clean_inline_markup(re.sub(r"^\s*(?:[-*]|\d+[.)])\s*", "", line).strip())
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if lowered.startswith("aplicacao pratica") or lowered.startswith("aplicação prática"):
                continue
            if len(cleaned.split()) < 3:
                continue
            items.append(cleaned)
    if len(items) < 3:
        fallback_items = [extract_numbered_content(item).strip() for item in fallback if item.strip()]
        while len(items) < 3 and len(items) < len(fallback_items):
            items.append(fallback_items[len(items)])
    while len(items) < 3:
        items.append(f"Acao pratica {len(items) + 1}")
    return items[:5]


def _first_sentence(text: str) -> str:
    normalized = normalize_whitespace(text)
    if not normalized:
        return "Licao principal: aplicar os conceitos com consistencia."
    sentence = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)[0].strip()
    if not sentence:
        return "Licao principal: aplicar os conceitos com consistencia."
    if sentence[-1] not in ".!?":
        sentence = f"{sentence}."
    return sentence


def _format_concepts_guided_section(
    section_text: str,
    concept_blocks: list[tuple[str, str, str]],
    concept_names: list[str],
) -> list[str]:
    lines: list[str] = []
    if concept_blocks:
        for idx, (name, explanation, example) in enumerate(concept_blocks):
            label = _alpha_label(idx)
            line = f"{label}. {strip_concept_prefix(name)}"
            if explanation:
                line += f": {explanation}"
            if example:
                line += f" Exemplo pratico: {example}"
            lines.append(normalize_whitespace(line))
    else:
        for idx, name in enumerate(concept_names):
            lines.append(f"{_alpha_label(idx)}. {strip_concept_prefix(_clean_inline_markup(name))}")

    if not lines:
        fallback_body = _clean_inline_markup(normalize_whitespace(section_text))
        if not fallback_body:
            return []
        return [f"3. {_SECTION_NAMES[3]}", fallback_body]

    return [f"3. {_SECTION_NAMES[3]}", *lines]


def _format_practical_guided_section(section_text: str, actions: list[str]) -> list[str]:
    lines: list[str] = [f"6. {_SECTION_NAMES[6]}"]
    intro = _extract_section_intro(section_text)
    if intro:
        lines.append(intro)
    for idx, action in enumerate(actions):
        lines.append(f"{_alpha_label(idx)}. {_clean_inline_markup(action)}")
    if len(lines) == 1:
        return []
    return lines


def _extract_section_intro(section_text: str) -> str:
    intro_lines: list[str] = []
    for raw_line in section_text.splitlines():
        line = normalize_whitespace(raw_line)
        if not line:
            continue
        if re.match(r"^\s*(?:\d+[.)]|[-*])\s+", line):
            continue
        lowered = line.lower()
        lowered = re.sub(r"^\s*(?:[-*•]\s*)+", "", lowered)
        if lowered.startswith("conceito:"):
            continue
        if lowered.startswith("explicacao:") or lowered.startswith("explicação:"):
            continue
        if lowered.startswith("exemplo:"):
            continue
        if lowered.startswith("aplicacao pratica") or lowered.startswith("aplicação prática"):
            continue
        intro_lines.append(_clean_inline_markup(line))
    return normalize_whitespace(" ".join(intro_lines))


def _strip_leading_quoted_title(text: str, title: str) -> str:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return ""
    title_clean = normalize_whitespace(title)
    if not title_clean:
        return cleaned

    variants = [
        f"\"{title_clean}\"",
        f"“{title_clean}”",
        f"'{title_clean}'",
        f"‘{title_clean}’",
    ]
    for quoted in variants:
        if cleaned.startswith(quoted):
            return (title_clean + cleaned[len(quoted) :]).lstrip()
    return cleaned


def _clean_inline_markup(text: str) -> str:
    cleaned = normalize_whitespace(text)
    cleaned = cleaned.replace("**", "").replace("__", "")
    cleaned = cleaned.replace("`", "")
    return normalize_whitespace(cleaned)


def _alpha_label(index: int) -> str:
    value = index
    label = ""
    while True:
        label = chr(ord("a") + (value % 26)) + label
        value = (value // 26) - 1
        if value < 0:
            break
    return label
