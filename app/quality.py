from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.lesson import Lesson
from app.utils import extract_numbered_content, first_word, normalize_for_similarity


_BANNED_EXPRESSIONS = [
    "no contexto de",
    "de forma passiva",
    "em ambientes acelerados",
    "esse formato acelera",
    "ao final, o objetivo",
]

_FOOTER_PATTERNS = [
    "gerado em ",
    "mba 15min",
]


@dataclass(frozen=True)
class QualityIssue:
    code: str
    message: str
    severity: str  # "warning" | "error"


@dataclass(frozen=True)
class QualityReport:
    issues: list[QualityIssue]

    @property
    def has_blocking_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)


def evaluate_lesson_quality(lesson: Lesson) -> QualityReport:
    issues: list[QualityIssue] = []
    issues.extend(_check_section_completeness(lesson))
    issues.extend(_check_footer_leakage(lesson))
    issues.extend(_check_repeated_paragraph_openings(lesson.guided_reading))
    issues.extend(_check_repeated_phrase_patterns(lesson))
    issues.extend(_check_banned_expressions(lesson))
    issues.extend(_check_concept_structure_similarity(lesson.concepts))
    return QualityReport(issues=issues)


def _check_section_completeness(lesson: Lesson) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    if len(lesson.concepts) < 1:
        issues.append(
            QualityIssue(
                code="missing_concepts",
                message="A secao de conceitos precisa conter ao menos 1 item.",
                severity="error",
            )
        )
    if len(lesson.practical_applications) != 3:
        issues.append(
            QualityIssue(
                code="missing_practical_apps",
                message="A secao de aplicacoes praticas precisa conter exatamente 3 itens.",
                severity="error",
            )
        )
    if not lesson.guided_reading:
        issues.append(
            QualityIssue(
                code="missing_guided_reading",
                message="A secao de leitura guiada esta vazia.",
                severity="error",
            )
        )
    return issues


def _check_footer_leakage(lesson: Lesson) -> list[QualityIssue]:
    body_text = " ".join(
        [
            lesson.central_idea,
            *lesson.guided_reading,
            *lesson.concepts,
            *lesson.practical_applications,
            lesson.reflection_question,
            lesson.optional_quote or "",
        ]
    ).lower()
    issues: list[QualityIssue] = []
    for token in _FOOTER_PATTERNS:
        if token in body_text:
            issues.append(
                QualityIssue(
                    code="footer_leakage",
                    message=f"Possivel vazamento de rodape no corpo: '{token.strip()}'.",
                    severity="error",
                )
            )
    return issues


def _check_repeated_paragraph_openings(paragraphs: list[str]) -> list[QualityIssue]:
    openings = [first_word(paragraph) for paragraph in paragraphs if paragraph.strip()]
    counts = Counter([opening for opening in openings if opening])
    repeated = [word for word, count in counts.items() if count > 1]
    if not repeated:
        return []
    return [
        QualityIssue(
            code="repeated_paragraph_opening",
            message=f"Aberturas repetidas em paragrafos: {', '.join(sorted(repeated))}.",
            severity="warning",
        )
    ]


def _check_repeated_phrase_patterns(lesson: Lesson) -> list[QualityIssue]:
    text = " ".join(
        [lesson.central_idea, *lesson.guided_reading, *lesson.concepts, *lesson.practical_applications]
    )
    words = re.findall(r"[A-Za-zÀ-ÿ]{4,}", text.lower())
    if len(words) < 3:
        return []
    trigrams = [" ".join(words[idx : idx + 3]) for idx in range(len(words) - 2)]
    counts = Counter(trigrams)
    repeated = [pattern for pattern, count in counts.items() if count >= 3]
    if not repeated:
        return []
    example = ", ".join(repeated[:3])
    return [
        QualityIssue(
            code="repeated_phrase_pattern",
            message=f"Padroes de frase repetidos detectados: {example}.",
            severity="warning",
        )
    ]


def _check_banned_expressions(lesson: Lesson) -> list[QualityIssue]:
    text = " ".join(
        [lesson.central_idea, *lesson.guided_reading, *lesson.concepts, *lesson.practical_applications]
    ).lower()
    issues: list[QualityIssue] = []
    for expression in _BANNED_EXPRESSIONS:
        if expression in text:
            issues.append(
                QualityIssue(
                    code="banned_expression",
                    message=f"Expressao repetitiva encontrada: '{expression}'.",
                    severity="warning",
                )
            )
    return issues


def _check_concept_structure_similarity(concepts: list[str]) -> list[QualityIssue]:
    cleaned = [normalize_for_similarity(extract_numbered_content(item)) for item in concepts if item.strip()]
    pairs: list[str] = []
    for left_idx in range(len(cleaned)):
        for right_idx in range(left_idx + 1, len(cleaned)):
            ratio = SequenceMatcher(a=cleaned[left_idx], b=cleaned[right_idx]).ratio()
            if ratio >= 0.86:
                pairs.append(f"{left_idx + 1}-{right_idx + 1}")
    if not pairs:
        return []
    return [
        QualityIssue(
            code="similar_concept_structure",
            message=f"Conceitos com estrutura muito parecida: {', '.join(pairs)}.",
            severity="warning",
        )
    ]
