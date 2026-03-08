from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, replace
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BookEntry:
    day: int
    title: str
    author: str
    theme: str
    key_ideas: list[str]
    practical_applications: list[str]
    reflection_question: str
    optional_quote: str | None = None


@dataclass(frozen=True)
class Lesson:
    day: int
    title: str
    author: str
    theme: str
    central_idea: str
    concepts: list[str]
    practical_applications: list[str]
    reflection_question: str
    guided_reading: list[str]
    summary_bullets: list[str]
    optional_quote: str | None = None

    def word_count(self) -> int:
        text_parts: list[str] = [
            self.central_idea,
            self.reflection_question,
            *self.concepts,
            *self.practical_applications,
            *self.guided_reading,
            *(self.summary_bullets or []),
        ]
        if self.optional_quote:
            text_parts.append(self.optional_quote)
        return sum(len(part.split()) for part in text_parts)


def load_books(path: Path) -> list[BookEntry]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    books = [BookEntry(**item) for item in payload]
    if len(books) != 365:
        raise ValueError("books_365.json precisa conter exatamente 365 itens.")

    days = {item.day for item in books}
    expected_days = set(range(1, 366))
    if days != expected_days:
        raise ValueError("books_365.json precisa ter dias de 1 a 365 sem lacunas.")
    return sorted(books, key=lambda item: item.day)


def get_entry_for_day(books: list[BookEntry], day: int) -> BookEntry:
    if day < 1 or day > 365:
        raise ValueError("Dia precisa estar entre 1 e 365.")
    return books[day - 1]


def generate_first_draft(entry: BookEntry) -> Lesson:
    return _build_base_lesson(entry)


def build_lesson(
    entry: BookEntry,
    openai_api_key: str | None = None,
    openai_model: str = "gpt-4.1-mini",
) -> Lesson:
    from app.formatter import lesson_from_refinement_text, lesson_to_refinement_text, normalize_lesson_lists
    from app.openai_refiner import refine_text_with_openai
    from app.quality import evaluate_lesson_quality
    from app.refiner import refine_lesson_local

    draft = generate_first_draft(entry)
    locally_refined = normalize_lesson_lists(refine_lesson_local(draft))

    candidate = locally_refined
    if openai_api_key:
        previous_key = os.getenv("OPENAI_API_KEY")
        previous_model = os.getenv("OPENAI_MODEL")
        try:
            os.environ["OPENAI_API_KEY"] = openai_api_key
            os.environ["OPENAI_MODEL"] = openai_model
            serialized = lesson_to_refinement_text(locally_refined)
            ai_refined_text = refine_text_with_openai(serialized)
            parsed = lesson_from_refinement_text(locally_refined, ai_refined_text)
            if parsed is None:
                logger.warning("Refino OpenAI retornou estrutura invalida; mantendo versao local.")
            else:
                candidate = normalize_lesson_lists(parsed)
        finally:
            if previous_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous_key
            if previous_model is None:
                os.environ.pop("OPENAI_MODEL", None)
            else:
                os.environ["OPENAI_MODEL"] = previous_model

    report = evaluate_lesson_quality(candidate)
    _log_quality_issues(report.issues)
    if report.has_blocking_errors:
        logger.warning("Qualidade bloqueante detectada; usando versao local refinada.")
        candidate = locally_refined

    min_words = min(900, locally_refined.word_count())
    if candidate.word_count() < min_words:
        logger.warning(
            "Refino final ficou curto demais (%s palavras); mantendo versao local.",
            candidate.word_count(),
        )
        return locally_refined

    if candidate.word_count() > 1600:
        logger.warning("Refino final excedeu 1600 palavras; mantendo versao local.")
        return locally_refined
    return candidate


def _build_base_lesson(entry: BookEntry) -> Lesson:
    ideas = _ensure_length(entry.key_ideas, 1, "Conceito essencial")
    applications = _ensure_length(entry.practical_applications, 3, "Aplicacao pratica recomendada")
    concepts = [f"{idx}. {idea}" for idx, idea in enumerate(ideas, start=1)]
    practical = [f"{idx}. {app}" for idx, app in enumerate(applications[:3], start=1)]
    guided_reading = _build_guided_reading(entry, ideas)
    summary = [
        f"Tese central: {entry.theme}.",
        f"Eixo conceitual dominante: {ideas[0]}.",
        "Sintese critica: progresso consistente supera mudancas bruscas.",
    ]
    central = (
        f"\"{entry.title}\", de {entry.author}, aborda \"{entry.theme}\" de forma direta: "
        "resultados grandes surgem da repeticao de pequenas decisoes corretas. Em vez de depender "
        "de motivacao intensa ou de mudancas radicais, o livro mostra um caminho de melhoria "
        "incremental, com foco em sistema, constancia e ajuste continuo. A leitura conecta ideia, "
        "mecanismo e aplicacao pratica, ajudando o leitor a transformar principio abstrato em rotina "
        "observavel no dia a dia."
    )

    lesson = Lesson(
        day=entry.day,
        title=entry.title,
        author=entry.author,
        theme=entry.theme,
        central_idea=central,
        concepts=concepts,
        practical_applications=practical,
        reflection_question=entry.reflection_question.strip(),
        guided_reading=guided_reading,
        summary_bullets=summary,
        optional_quote=entry.optional_quote.strip() if entry.optional_quote else None,
    )

    return _ensure_target_word_count(lesson)


def _build_guided_reading(entry: BookEntry, ideas: list[str]) -> list[str]:
    paragraphs: list[str] = []
    paragraphs.append(
        f"Conceitos centrais de \"{entry.title}\": o livro parte de \"{entry.theme}\" para mostrar "
        "que o resultado final e consequencia do processo repetido. A leitura fica mais util quando "
        "cada conceito e tratado com quatro perguntas: o que significa, por que funciona, como aparece "
        "na pratica e qual passo concreto voce pode testar hoje."
    )
    anchors = _ensure_length(entry.practical_applications, 3, "Aplicacao pratica recomendada")
    for idx, idea in enumerate(ideas, start=1):
        anchor = anchors[(idx - 1) % len(anchors)]
        paragraphs.append(_build_concept_explainer(entry.title, idea, idx, anchor))
    paragraphs.append(
        "Resumo em uma frase: desempenho consistente raramente nasce de uma decisao heroica; ele surge "
        "da soma de pequenas melhorias praticadas por tempo suficiente para gerar efeito composto."
    )
    return paragraphs


def _build_concept_explainer(title: str, idea: str, idx: int, anchor: str) -> str:
    clean_idea = idea.strip().rstrip(".")
    lowered = clean_idea.lower()

    if idx == 1 and _looks_like_compound_growth_idea(lowered):
        return (
            f"Conceito {idx} de {title}: {clean_idea}. Esse conceito e um dos pilares da obra. "
            "A logica e simples: pequenas melhorias diarias se acumulam e criam um salto de resultado "
            "ao longo do tempo, de forma parecida com juros compostos. Exemplo numerico classico: "
            "1.01^365 ~= 37, enquanto 0.99^365 ~= 0.03. Em outras palavras, pequenas escolhas positivas "
            "repetidas elevam desempenho, e pequenas escolhas negativas repetidas corroem progresso. "
            f"Passo pratico de hoje: {anchor}"
        )

    openings = [
        f"Conceito {idx} de {title}",
        f"Seguindo o raciocinio do livro, o conceito {idx}",
        f"Ja no conceito {idx}",
        f"No conceito {idx}",
        f"Por fim, no conceito {idx}",
    ]
    opening = openings[(idx - 1) % len(openings)]
    mechanism = _concept_mechanism_hint(lowered)
    example = _concept_example_hint(lowered)

    return (
        f"{opening}: {clean_idea}. Em linguagem direta, {mechanism} "
        f"Exemplo pratico: {example} Passo pratico de hoje: {anchor}"
    )


def _looks_like_compound_growth_idea(idea: str) -> bool:
    triggers = ["melhoria", "crescimento composto", "acumul", "1%", "composto"]
    return any(token in idea for token in triggers)


def _concept_mechanism_hint(idea: str) -> str:
    if "ambiente" in idea:
        return (
            "o ambiente reduz ou aumenta atrito para o comportamento. Quando a acao desejada fica "
            "visivel, simples e acessivel, a execucao depende menos de motivacao momentanea."
        )
    if "identidade" in idea:
        return (
            "o comportamento tende a se manter quando reforca a identidade que a pessoa quer construir. "
            "A pergunta deixa de ser 'o que eu quero atingir' e vira 'quem eu quero me tornar'."
        )
    if "sistema" in idea or "meta" in idea:
        return (
            "metas apontam direcao, mas sistema define repeticao. Sem rotina clara, o objetivo vira "
            "intencao; com rotina, vira progresso mensuravel."
        )
    if "rastreamento" in idea or "visual" in idea:
        return (
            "feedback visual imediato aumenta consistencia, porque torna a execucao observavel e ajuda "
            "a interromper quedas antes que virem padrao."
        )
    return (
        "o principio transforma uma ideia ampla em comportamento repetivel. A forca do conceito aparece "
        "quando ele e aplicado em ciclos curtos de teste, medicao e ajuste."
    )


def _concept_example_hint(idea: str) -> str:
    if "ambiente" in idea:
        return (
            "deixar livro na mesa e celular fora do alcance na hora de estudar aumenta a chance de leitura "
            "sem exigir disciplina heroica."
        )
    if "identidade" in idea:
        return (
            "quem quer ser 'uma pessoa saudavel' pode manter um treino curto diario, mesmo em dias corridos, "
            "para reforcar esse auto-conceito."
        )
    if "sistema" in idea or "meta" in idea:
        return (
            "em vez de focar em 'escrever um livro', definir 300 palavras por dia cria progresso estavel e "
            "acumulativo."
        )
    if "rastreamento" in idea or "visual" in idea:
        return "marcar um calendario apos cada execucao do habito ajuda a manter sequencia e detectar recaidas."
    return "reservar 15 minutos diarios para a mesma atividade gera acumulacao visivel apos algumas semanas."


def _ensure_length(items: list[str], minimum: int, prefix: str) -> list[str]:
    result = [item.strip() for item in items if item.strip()]
    while len(result) < minimum:
        result.append(f"{prefix} {len(result) + 1}")
    return result


def _ensure_target_word_count(lesson: Lesson) -> Lesson:
    additions = [
        (
            "Aplicacao em 7 dias: escolha um habito de ate 10 minutos e execute no mesmo horario durante "
            "uma semana. No fim do periodo, registre tres pontos: o que ficou facil, onde houve atrito e "
            "qual ajuste reduz a chance de falha na semana seguinte. No dia 1, foque apenas em iniciar no "
            "horario combinado. Do dia 2 ao dia 4, mantenha o mesmo gatilho para reduzir decisao. Do dia 5 "
            "ao dia 7, acompanhe continuidade e descreva em uma frase o que ajudou ou atrapalhou a execucao."
        ),
        (
            "Erros comuns ao aplicar os conceitos: tentar mudar tudo de uma vez, depender apenas de motivacao, "
            "nao medir execucao e abandonar o processo apos poucos dias sem resultado visivel. O livro reforca "
            "que consistencia e mais importante que intensidade pontual. Outro erro frequente e definir meta "
            "ambiciosa sem desenhar o contexto de execucao: sem horario, local e gatilho claros, a rotina vira "
            "boa intencao. Correcao pratica: reduzir escopo, manter frequencia e revisar o sistema semanalmente."
        ),
        (
            "Checklist de consolidacao: manter o gatilho do habito visivel, reduzir friccao para iniciar, "
            "registrar a execucao diariamente e revisar o sistema uma vez por semana. Essa rotina simples "
            "costuma gerar melhoria sustentavel sem exigir mudancas radicais. Para manter aderencia, escolha "
            "um indicador simples de processo (dias executados, minutos dedicados ou repeticoes concluidas) "
            "e um indicador de resultado (qualidade percebida, velocidade ou estabilidade)."
        ),
        (
            "Modelo de revisao semanal: o que funcionou, o que travou e qual unico ajuste entra na proxima "
            "semana. Esse fechamento evita acumulacao de tentativas desconectadas e cria aprendizado pratico. "
            "Com revisoes curtas e constantes, o sistema evolui sem ruptura e sem depender de motivacao alta."
        ),
    ]
    updated = lesson
    idx = 0
    while updated.word_count() < 900 and idx < len(additions):
        updated = replace(updated, guided_reading=[*updated.guided_reading, additions[idx]])
        idx += 1
    if updated.word_count() < 900:
        updated = replace(
            updated,
            guided_reading=[
                *updated.guided_reading,
                (
                    "Ajuste final: escolha uma acao objetiva para hoje, acompanhe sua execucao e "
                    "registre o aprendizado em linguagem simples para consolidar a evolucao."
                ),
            ],
        )
    return updated


def _log_quality_issues(issues: list[object]) -> None:
    for issue in issues:
        severity = getattr(issue, "severity", "warning")
        message = getattr(issue, "message", str(issue))
        code = getattr(issue, "code", "quality_issue")
        if severity == "error":
            logger.error("Quality [%s]: %s", code, message)
        else:
            logger.warning("Quality [%s]: %s", code, message)
